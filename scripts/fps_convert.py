"""Frame-rate engine: 24 / 25 / 30 / 50 / 60 / 120 (and anything else) in both directions, slow motion, motion blur.

  python fps_convert.py probe SRC.mp4                          # real fps, VFR, duplicated frames (effective fps)
  python fps_convert.py convert SRC.mp4 OUT.mp4 --fps 24 [--start 10 --dur 5] [--mode auto] [--shutter 180]
                        [--slowmo 1] [--engine rife|flow|blend] [--size 1920x1080] [--crf 16]

How --mode auto decides (src -> target):
  same rate .................. copy frames (no processing)
  integer DOWN (120->24, 60->30, 50->25, 120->60)
                              keep every k-th frame; with --shutter > 0 average the frames a real 180-degree shutter
                              would have exposed (tmix) -> natural motion blur, no strobing
  near rate (25<->24, 30<->29.97, 60<->59.94)
                              conform: play every frame, change speed by <= 4.2 % (audio must be re-timed separately)
  non-integer DOWN (60->24, 30->24, 60->25, 30->25, 120->25)
                              RIFE re-samples to exactly even capture times (no 2:3 judder); with shutter blur when
                              src >= 2x target (RIFE x2 up, blend, step)
  UP (24->60, 30->60, 60->120, 25->50)
                              RIFE motion interpolation (AI, GPU). Fallback --engine flow: ffmpeg minterpolate (MCI)
  --slowmo S                  S x slower. A 120p source at --fps 24 --slowmo 5 is true slow motion (no invented frames);
                              otherwise missing frames are interpolated with RIFE.
RIFE binary: env RIFE_BIN or ~/tools/rife/*/rife-ncnn-vulkan.exe (install.ps1 downloads it)
"""
import argparse, glob, json, os, re, shutil, subprocess, sys, tempfile
from fractions import Fraction

RIFE_BIN = os.environ.get('RIFE_BIN') or next(iter(glob.glob(os.path.expanduser('~/tools/rife/*/rife-ncnn-vulkan.exe'))), '')
STD = [23.976, 24, 25, 29.97, 30, 47.952, 48, 50, 59.94, 60, 100, 119.88, 120, 240]


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf8', errors='replace', **kw)
    if r.returncode: raise RuntimeError(' '.join(map(str, cmd[:6])) + '...\n' + r.stderr[-1500:])
    return r


def nominal(f):
    return min(STD, key=lambda s: abs(s - f)) if f else f


def probe(src, seconds=8.0):
    r = run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
             'stream=r_frame_rate,avg_frame_rate,width,height:format=duration', '-of', 'json', src])
    d = json.loads(r.stdout); s = d['streams'][0]
    fr = lambda x: float(Fraction(x)) if x and x != '0/0' else 0.0
    rf, af = fr(s['r_frame_rate']), fr(s['avg_frame_rate'])
    # padding detection: duplicated frames that appear WHILE the picture moves, on a regular cycle
    # (24p in 30p = 1 dup every 5 frames; 30p in 60p = every 2nd). Still / slow shots are not padding.
    import numpy as np
    dur = float(d['format']['duration']); t0 = max(0.0, min(dur / 2 - seconds / 2, dur - seconds))
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t0:.2f}', '-t', str(seconds), '-i', src, '-an', '-vf', 'scale=96:54,format=gray',
                          '-f', 'rawvideo', '-'], capture_output=True).stdout
    G = np.frombuffer(raw, np.uint8).reshape(-1, 54, 96).astype(np.float32)
    dif = np.abs(np.diff(G, axis=0)).mean((1, 2)) if len(G) > 2 else np.zeros(1)
    k = 7; loc = np.array([np.median(dif[max(0, i - k):i + k + 1]) for i in range(len(dif))])
    moving = loc > 0.2
    dup = moving & (dif < 0.15 * loc)
    r = dup.sum() / max(1, moving.sum())
    idx = np.where(dup)[0]; periodic = len(idx) >= 4 and np.std(np.diff(idx)) < 0.6
    fps0 = af or rf
    eff = fps0 * (1 - r) if (moving.sum() > 20 and r > 0.12 and periodic) else fps0
    return {'fps': round(fps0, 3), 'r_fps': round(rf, 3), 'vfr': abs(rf - af) > 0.01, 'w': s['width'], 'h': s['height'],
            'duration': dur, 'moving_frames': int(moving.sum()), 'dup_ratio_moving': round(float(r), 3),
            'unique_ratio': round(eff / fps0, 3) if fps0 else 1.0, 'effective_fps': round(eff, 2),
            'note': ('khung đệm đều đặn - nội dung thật ~%.2f fps' % eff) if eff < fps0 * 0.95 else ''}


def plan(fs, ft, slowmo=1.0):
    """Return (method, detail) for converting content at fs to ft (after slow motion)."""
    fs_eff = fs / slowmo                     # source frames available per output second
    r = fs_eff / ft
    if abs(r - 1) < 0.002: return 'copy', 'same rate'
    if r > 1 and abs(r - round(r)) < 0.01: return 'step', int(round(r))
    if abs(r - 1) <= 0.042: return 'conform', r
    if r > 1: return 'rife_down', r
    return 'rife_up', r


def _scale(size):
    if not size: return []
    w, h = size.split('x')
    return [f'scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos', f'crop={w}:{h}', 'setsar=1']


def _enc(crf, ft):
    return ['-c:v', 'libx264', '-crf', str(crf), '-preset', 'slow', '-pix_fmt', 'yuv420p', '-g', str(int(round(ft * 2))),
            '-movflags', '+faststart']


def rife(in_dir, out_dir, n_out, model='rife-v4.6'):
    if not RIFE_BIN or not os.path.exists(RIFE_BIN): raise RuntimeError('RIFE chưa cài - dùng --engine flow hoặc cài theo --help')
    mdir = os.path.join(os.path.dirname(RIFE_BIN), model)
    if not os.path.isdir(mdir):
        cands = sorted(d for d in os.listdir(os.path.dirname(RIFE_BIN)) if d.startswith('rife-v4'))
        mdir = os.path.join(os.path.dirname(RIFE_BIN), cands[-1])
    os.makedirs(out_dir, exist_ok=True)
    run([RIFE_BIN, '-i', in_dir, '-o', out_dir, '-n', str(n_out), '-m', mdir, '-f', '%08d.png', '-j', '2:2:2'])


def convert(src, out, ft, start=None, dur=None, mode='auto', shutter=180, slowmo=1.0, engine='rife', size=None, crf=16, verbose=True):
    if os.path.exists(out): raise SystemExit(f'{out} đã tồn tại')
    info = probe(src); fs = info['fps']
    pre = []
    if info['unique_ratio'] < 0.9:            # e.g. 24p content padded to 30p: remove the padding first
        pre.append(f'mpdecimate,setpts=N/{info["effective_fps"]:.3f}/TB'); fs = nominal(info['effective_fps'])
    elif info['vfr']:
        pre.append(f'fps={nominal(fs)}'); fs = nominal(fs)
    meth, det = plan(fs, ft, slowmo) if mode == 'auto' else (mode, None)
    if meth in ('rife_down', 'rife_up') and engine != 'rife': meth = 'flow' if engine == 'flow' else 'blendconv'
    seek = (['-ss', f'{start:.3f}'] if start is not None else [])
    tdur = (['-t', f'{dur * 1.0 / 1:.3f}'] if dur is not None else [])     # dur = OUTPUT seconds; source span = dur/slowmo
    if dur is not None: tdur = ['-t', f'{dur / slowmo + 2.0 / fs:.3f}']
    sm = [f'setpts={slowmo}*PTS'] if slowmo != 1.0 else []
    outdur = ['-t', f'{dur:.3f}'] if dur is not None else []
    if verbose: print(f'{os.path.basename(src)}: {fs} fps -> {ft} fps, slowmo x{slowmo}: {meth} {det if det else ""} {info["note"]}')
    if meth in ('copy', 'conform'):
        # copy: frames already at ft after slow motion; conform: play every source frame at ft (speed change <= 4 %)
        vf = pre + ([f'setpts=PTS*{fs * slowmo / ft:.6f}'] if meth == 'conform' else sm) + [f'fps={ft}'] + _scale(size)
        run(['ffmpeg', '-v', 'error', '-y', *seek, *tdur, '-i', src, '-an', '-vf', ','.join(vf), *outdur, *_enc(crf, ft), out])
    elif meth == 'step':
        k = det; m = max(1, int(round(k * shutter / 360.0)))
        blur = [f'tmix=frames={m}:weights=' + "'" + ' '.join(['1'] * m) + "'"] if m > 1 else []
        vf = pre + sm + [f'fps={fs}'] + blur + [f'framestep={k}', f'setpts=N/{ft}/TB'] + _scale(size)
        run(['ffmpeg', '-v', 'error', '-y', *seek, *tdur, '-i', src, '-an', '-vf', ','.join(vf), '-r', str(ft), *outdur, *_enc(crf, ft), out])
    elif meth == 'flow':
        vf = pre + sm + [f'minterpolate=fps={ft}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1'] + _scale(size)
        run(['ffmpeg', '-v', 'error', '-y', *seek, *tdur, '-i', src, '-an', '-vf', ','.join(vf), *outdur, *_enc(crf, ft), out])
    elif meth == 'blendconv':
        vf = pre + sm + [f'framerate=fps={ft}:interp_start=0:interp_end=255:scene=8.2'] + _scale(size)
        run(['ffmpeg', '-v', 'error', '-y', *seek, *tdur, '-i', src, '-an', '-vf', ','.join(vf), *outdur, *_enc(crf, ft), out])
    else:   # RIFE paths
        tmp = tempfile.mkdtemp(prefix='rife_'); a, b = os.path.join(tmp, 'in'), os.path.join(tmp, 'out'); os.makedirs(a)
        run(['ffmpeg', '-v', 'error', '-y', *seek, *tdur, '-i', src, '-an', '-vf', ','.join(pre + [f'fps={fs}'] + (_scale(size) or ['null'])),
             os.path.join(a, '%08d.png')])
        n_in = len(os.listdir(a)); span = n_in / fs                       # seconds of source
        out_secs = span * slowmo
        if meth == 'rife_down' and shutter > 0 and det >= 2:
            # up to an integer multiple of ft (k*ft), then blend k*shutter/360 frames and step k -> even + motion blur
            # k*ft intermediate rate so that m = k*shutter/360 >= 2 frames are blended (180 deg -> 96 fps for 24p)
            import math
            k = max(int(math.ceil(det)), int(math.ceil(720.0 / shutter))); n_out = int(round(out_secs * ft * k))
            rife(a, b, n_out)
            m = max(1, int(round(k * shutter / 360.0)))
            blur = [f'tmix=frames={m}:weights=' + "'" + ' '.join(['1'] * m) + "'"] if m > 1 else []
            vf = blur + [f'framestep={k}', f'setpts=N/{ft}/TB']
            run(['ffmpeg', '-v', 'error', '-y', '-framerate', str(ft * k), '-i', os.path.join(b, '%08d.png'), '-vf', ','.join(vf),
                 '-r', str(ft), *outdur, *_enc(crf, ft), out])
        else:
            n_out = int(round(out_secs * ft)); rife(a, b, n_out)
            run(['ffmpeg', '-v', 'error', '-y', '-framerate', str(ft), '-i', os.path.join(b, '%08d.png'), *outdur, *_enc(crf, ft), out])
        shutil.rmtree(tmp, ignore_errors=True)
    return meth


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('probe'); p.add_argument('src', nargs='+')
    c = sp.add_parser('convert'); c.add_argument('src'); c.add_argument('out'); c.add_argument('--fps', type=float, required=True)
    c.add_argument('--start', type=float); c.add_argument('--dur', type=float); c.add_argument('--mode', default='auto')
    c.add_argument('--shutter', type=float, default=180); c.add_argument('--slowmo', type=float, default=1.0)
    c.add_argument('--engine', default='rife', choices=['rife', 'flow', 'blend']); c.add_argument('--size'); c.add_argument('--crf', type=int, default=16)
    a = ap.parse_args()
    if a.cmd == 'probe':
        for s in a.src: print(s, json.dumps(probe(s), ensure_ascii=False))
    else:
        convert(a.src, a.out, a.fps, a.start, a.dur, a.mode, a.shutter, a.slowmo, a.engine, a.size, a.crf)


if __name__ == '__main__':
    main()
