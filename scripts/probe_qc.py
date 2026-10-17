"""QC / inventory for video files.

  python probe_qc.py FILM.mp4 [--json out.json] [--no-judder]     # full QC of an edit
  python probe_qc.py --inventory SRC1.mp4 SRC2.mov ...             # quick table of sources (fps, VFR, size, cuts)

Checks: stream info (fps, VFR, resolution, duration, frame count), hard cuts, stray islands (1-4 frames between two
cuts that differ from both neighbours), single black/white flashes, duplicated / frozen frames inside moving shots,
camera-motion judder per shot (dense optical flow, 0 = perfectly even), letterbox, loudness (EBU R128 I, LRA, true peak).
"""
import argparse, json, re, subprocess, sys
import numpy as np


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, encoding='utf8', errors='replace', **kw)


def probe(path):
    r = run(['ffprobe', '-v', 'error', '-show_entries',
             'stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,nb_frames,sample_rate,channels'
             ':format=duration,bit_rate', '-of', 'json', path])
    d = json.loads(r.stdout or '{}')
    v = next((s for s in d.get('streams', []) if s['codec_type'] == 'video'), {})
    a = next((s for s in d.get('streams', []) if s['codec_type'] == 'audio'), {})
    fr = lambda x: (lambda p: float(p[0]) / float(p[1]) if len(p) == 2 and float(p[1]) else 0.0)(str(x or '0/1').split('/'))
    rf, af = fr(v.get('r_frame_rate')), fr(v.get('avg_frame_rate'))
    return {'path': path, 'duration': float(d.get('format', {}).get('duration', 0) or 0),
            'width': v.get('width'), 'height': v.get('height'), 'vcodec': v.get('codec_name'),
            'fps': round(af or rf, 3), 'r_fps': round(rf, 3), 'vfr': bool(rf and af and abs(rf - af) > 0.01),
            'nb_frames': int(v['nb_frames']) if str(v.get('nb_frames', '')).isdigit() else None,
            'acodec': a.get('codec_name'), 'sr': a.get('sample_rate'), 'ch': a.get('channels')}


def frames_small(path, W=96, H=54, crop='crop=iw:ih*0.78:0:0'):
    """Low-res RGB frames (bottom 22 % cropped away so burnt-in subtitles do not count as cuts)."""
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', path, '-an', '-vf', f'{crop},scale={W}:{H},format=rgb24',
                          '-f', 'rawvideo', '-'], stdout=subprocess.PIPE)
    buf = p.stdout.read(); p.wait()
    return np.frombuffer(buf, np.uint8).reshape(-1, H, W, 3).astype(np.float32)


def flow_steps(path, W=320, H=180):
    """Median optical-flow magnitude between consecutive frames (pixels, scaled to 1920 width)."""
    import cv2
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', path, '-an', '-vf',
                          f'crop=iw:ih*0.78:0:0,scale={W}:{H},format=gray', '-f', 'rawvideo', '-'], stdout=subprocess.PIPE)
    prev, out = None, []
    while True:
        b = p.stdout.read(W * H)
        if len(b) < W * H: break
        f = np.frombuffer(b, np.uint8).reshape(H, W)
        if prev is not None:
            fl = cv2.calcOpticalFlowFarneback(prev, f, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            out.append(float(np.median(np.hypot(fl[..., 0], fl[..., 1]))) * 1920 / W)
        prev = f
    p.wait()
    return np.array(out)


def judder(st):
    """Unevenness of camera speed vs its local trend, over moving frames only. None if the shot barely moves."""
    k = 5
    if len(st) < 2 * k + 6: return None
    tr = np.convolve(st, np.ones(k) / k, 'same')
    m = tr[k:-k] > 0.4
    if m.sum() < 8: return None
    v, t = st[k:-k][m], tr[k:-k][m]
    return float(np.mean(np.abs(v - t)) / (np.mean(t) + 1e-6))


def cadence_ratio(st):
    ev, od = st[0::2], st[1::2]; n = min(len(ev), len(od))
    if n < 6 or np.median(st) < 0.4: return None
    r = float(np.median((ev[:n] + 1e-3) / (od[:n] + 1e-3)))
    return max(r, 1 / r)


def loudness(path):
    r = run(['ffmpeg', '-nostats', '-i', path, '-vn', '-af', 'ebur128=peak=true', '-f', 'null', '-'])
    tail = r.stderr[r.stderr.rfind('Summary'):]
    g = lambda pat: (lambda m: float(m.group(1)) if m else None)(re.search(pat, tail))
    return {'I_LUFS': g(r'I:\s+(-?[\d.]+) LUFS'), 'LRA': g(r'LRA:\s+(-?[\d.]+) LU'), 'TP_dBFS': g(r'Peak:\s+(-?[\d.]+) dBFS')}


def cuts_of(fr, thr=28.0):
    d = np.r_[0, np.abs(np.diff(fr, axis=0)).mean((1, 2, 3))]
    return d, [i for i in range(1, len(d)) if d[i] > thr]


def qc(path, do_judder=True):
    info = probe(path); fps = info['fps'] or 25.0
    fr = frames_small(path)
    d, cuts = cuts_of(fr)
    lum = fr.mean((1, 2, 3))
    find = []
    for a, b in zip(cuts, cuts[1:]):
        if b - a <= 4 and np.abs(fr[b] - fr[a - 1]).mean() > 20:
            find.append({'type': 'stray', 'frame': a, 'len': b - a, 't': round(a / fps, 2)})
    for i in range(1, len(lum) - 1):
        if (lum[i] < 8 and lum[i - 1] > 30 and lum[i + 1] > 30) or (lum[i] > 235 and lum[i - 1] < 200 and lum[i + 1] < 200):
            find.append({'type': 'flash', 'frame': i, 't': round(i / fps, 2)})
    # shots
    bounds = [0] + cuts + [len(fr)]
    shots = [{'start': round(a / fps, 2), 'end': round(b / fps, 2), 'dur': round((b - a) / fps, 2), 'f0': a, 'f1': b}
             for a, b in zip(bounds, bounds[1:]) if b > a]
    st = flow_steps(path) if do_judder else None
    for s in shots:
        if st is not None:
            seg = st[s['f0']:max(s['f0'], s['f1'] - 1)]
            j = judder(seg); s['judder'] = None if j is None else round(j, 3)
            c = cadence_ratio(seg); s['cadence'] = None if c is None else round(c, 2)
            mv = float(np.median(seg)) if len(seg) else 0.0
            s['motion'] = round(mv, 2)
            if mv > 0.6:   # moving shot: duplicated frames = near-zero step between moving neighbours
                z = [s['f0'] + 1 + k for k in range(1, len(seg) - 1) if seg[k] < 0.08 * mv and seg[k - 1] > 0.5 * mv and seg[k + 1] > 0.5 * mv]
                if z: find.append({'type': 'dup', 'frames': z[:10], 't': round(z[0] / fps, 2)})
                tailz = 0
                for v in seg[::-1]:
                    if v < 0.08 * mv: tailz += 1
                    else: break
                if tailz >= 3 and s['end'] < info['duration'] - 0.5:   # eased stops at the very end are not freezes
                    find.append({'type': 'freeze_tail', 'frames': tailz, 't': s['end']})
        if s['dur'] > 8.0: find.append({'type': 'long_shot', 'dur': s['dur'], 't': s['start']})
    # long black stretches (not counting the fade-in / fade-out second at each end)
    rb = run(['ffmpeg', '-v', 'info', '-i', path, '-an', '-vf', 'blackdetect=d=0.4:pix_th=0.08', '-f', 'null', '-'])
    for a0, a1 in re.findall(r'black_start:([\d.]+) black_end:([\d.]+)', rb.stderr):
        a0, a1 = float(a0), float(a1)
        if a1 > 1.2 and a0 < info['duration'] - 1.2 and a1 - a0 >= 0.4:
            find.append({'type': 'black', 't': round(a0, 2), 'dur': round(a1 - a0, 2)})
    # letterbox
    r = run(['ffmpeg', '-v', 'info', '-i', path, '-an', '-vf', 'select=not(mod(n\\,50)),cropdetect=24:16:0', '-frames:v', '40', '-f', 'null', '-'])
    crops = re.findall(r'crop=(\d+):(\d+):(\d+):(\d+)', r.stderr)
    lb = None
    if crops and info['width']:
        w, h, _, _ = map(int, crops[-1])
        if h < info['height'] * 0.95 or w < info['width'] * 0.95: lb = f'{w}x{h}'
    js = [s['judder'] for s in shots if s.get('judder') is not None]
    dur_w = [s['dur'] for s in shots if s.get('judder') is not None]
    summ = {'frames_read': len(fr), 'cuts': len(cuts), 'shots': len(shots), 'moving_shots': len(js),
            'judder_median': round(float(np.median(js)), 3) if js else None,
            'judder_p90': round(float(np.percentile(js, 90)), 3) if js else None,
            'judder_time_weighted': round(float(np.average(js, weights=dur_w)), 3) if js else None,
            'uneven_cadence_shots': sum(1 for s in shots if (s.get('cadence') or 1) > 1.2),
            'letterbox': lb}
    if info['acodec']: summ.update(loudness(path))
    return {'info': info, 'summary': summ, 'findings': find, 'shots': shots}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('files', nargs='+'); ap.add_argument('--json'); ap.add_argument('--inventory', action='store_true')
    ap.add_argument('--no-judder', action='store_true')
    a = ap.parse_args()
    if a.inventory:
        rows = []
        for f in a.files:
            i = probe(f); fr = frames_small(f, 64, 36); _, c = cuts_of(fr)
            i['cuts'] = len(c); rows.append(i)
            print(f"{f}\n   {i['width']}x{i['height']} {i['vcodec']} fps={i['fps']} {'VFR!' if i['vfr'] else 'CFR'} "
                  f"dur={i['duration']:.2f}s frames={i['nb_frames']} cuts={i['cuts']} audio={i['acodec']} {i['sr']}Hz x{i['ch']}")
        if a.json: json.dump(rows, open(a.json, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
        return
    for f in a.files:
        r = qc(f, not a.no_judder); i, s = r['info'], r['summary']
        print(f"== {f}\n   {i['width']}x{i['height']} fps={i['fps']} {'VFR!' if i['vfr'] else 'CFR'} dur={i['duration']:.2f}s "
              f"frames={i['nb_frames']} (read {s['frames_read']})")
        print(f"   cuts={s['cuts']} shots={s['shots']} moving={s['moving_shots']} judder median={s['judder_median']} "
              f"p90={s['judder_p90']} time-weighted={s['judder_time_weighted']} uneven-cadence shots={s['uneven_cadence_shots']}")
        if 'I_LUFS' in s: print(f"   loudness I={s['I_LUFS']} LUFS  LRA={s['LRA']}  TP={s['TP_dBFS']} dBFS   letterbox={s['letterbox']}")
        bad = [x for x in r['findings'] if x['type'] != 'long_shot']
        print(f"   findings: {len(bad)} errors, {len(r['findings']) - len(bad)} long shots")
        for x in r['findings']: print('     ', x)
        worst = sorted([x for x in r['shots'] if x.get('judder') is not None], key=lambda x: -x['judder'])[:5]
        for x in worst: print(f"      judder {x['judder']:.3f} cadence {x['cadence']} motion {x['motion']} @ {x['start']}-{x['end']}s")
        if a.json: json.dump(r, open(a.json, 'w', encoding='utf8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
