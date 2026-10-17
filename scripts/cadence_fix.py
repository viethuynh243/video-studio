"""Re-time one shot to an even camera-motion cadence with dense optical flow.

Use when a 60p/50p/30p source has been (or would be) decimated to 24/25 fps and pans look like "steps":
the kept frames were captured at uneven times (60->24 keeps every 2nd/3rd frame; 30->24 drops 1 in 5).

  python cadence_fix.py SRC.mp4 --start 12.0 --frames 120 --fps 24 OUT.mp4 [--mode auto|adaptive|23a|23b|30d0..30d3]
                        [--vf "crop=...,scale=1920:1080"] [--crf 16]

mode auto     : try uniform / 2:3 (two phases) / 30->24 (four phases) patterns on the source already decimated to
                the target fps, keep the one that makes speed most even (falls back to plain copy if uniform wins)
mode adaptive : estimate capture times from the motion itself (any irregular pattern)
Prints the chosen pattern and the judder before/after. Always look at the output frame by frame once.
"""
import argparse, subprocess
import numpy as np
import cv2


def read(path, s, n, fps, vf, W, H):
    chain = ([vf] if vf else []) + [f'fps={fps}', f'scale={W}:{H}:flags=lanczos']
    r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{s:.3f}', '-i', path, '-an', '-vf', ','.join(chain),
                        '-frames:v', str(n), '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], capture_output=True)
    return np.frombuffer(r.stdout, np.uint8).reshape(-1, H, W, 3)


def steps(F):
    sm = [cv2.cvtColor(cv2.resize(f, (480, 270), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY) for f in F]
    out = []
    for a, b in zip(sm[:-1], sm[1:]):
        fl = cv2.calcOpticalFlowFarneback(a, b, None, 0.5, 3, 21, 3, 5, 1.2, 0)
        out.append(float(np.median(np.hypot(fl[..., 0], fl[..., 1]))) * 4)
    return np.array(out)


def unevenness(v):
    k = 5; tr = np.convolve(v, np.ones(k) / k, 'same'); m = tr[k:-k] > 0.4
    if m.sum() < 8: return 0.0
    return float(np.mean(np.abs(v[k:-k][m] - tr[k:-k][m])) / (np.mean(tr[k:-k][m]) + 1e-6))


def patterns(fps):
    c = {'uniform': [1.0], '23a': [1.2, 0.8], '23b': [0.8, 1.2]}
    base = [1, 1, 1, 2]
    for p in range(4):
        pat = base[p:] + base[:p]; c[f'30d{p}'] = [x * 24 / 30 for x in pat]
    return c


def capture_times(st, mode, fps):
    n = len(st) + 1
    if mode == 'adaptive':
        k = 5; tr = np.convolve(st, np.ones(k) / k, 'same'); dt = np.ones(len(st)); mv = tr > 0.4
        dt[mv] = np.clip(st[mv] / (tr[mv] + 1e-6), 0.55, 1.45); dt *= len(st) / dt.sum()
        return np.concatenate([[0.0], np.cumsum(dt)]), 'adaptive', None
    cands = patterns(fps)
    def score(p):
        dt = np.array([p[i % len(p)] for i in range(len(st))]); return unevenness(st / dt)
    if mode == 'auto':
        sc = {k: score(v) for k, v in cands.items()}; best = min(sc, key=sc.get)
        if best == 'uniform' or sc[best] > 0.9 * sc['uniform']: best = 'uniform'
    else:
        best, sc = mode, {mode: score(cands[mode]), 'uniform': score(cands['uniform'])}
    p = cands[best]
    return np.concatenate([[0.0], np.cumsum([p[i % len(p)] for i in range(n - 1)])]), best, sc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src'); ap.add_argument('out'); ap.add_argument('--start', type=float, required=True)
    ap.add_argument('--frames', type=int, required=True); ap.add_argument('--fps', type=float, default=24)
    ap.add_argument('--mode', default='auto'); ap.add_argument('--vf', default='')
    ap.add_argument('--size', default='1920x1080'); ap.add_argument('--crf', type=int, default=16)
    a = ap.parse_args()
    W, H = map(int, a.size.split('x'))
    F = read(a.src, a.start, a.frames + 6, a.fps, a.vf, W, H)
    st = steps(F)
    t, mode, sc = capture_times(st, a.mode, a.fps)
    print('pattern:', mode, 'scores:', {k: round(v, 3) for k, v in (sc or {}).items()} if isinstance(sc, dict) else '')
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(a.fps),
                            '-i', '-', '-c:v', 'libx264', '-crf', str(a.crf), '-preset', 'slow', '-pix_fmt', 'yuv420p', a.out],
                           stdin=subprocess.PIPE)
    gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    small = lambda im: cv2.cvtColor(cv2.resize(im, (W // 2, H // 2), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    cache, out_frames = {}, []
    for i in range(a.frames):
        T = float(i) * (t[-1] / (len(t) - 1)) if mode == 'adaptive' else float(i) * np.mean(np.diff(t))
        k = int(min(max(np.searchsorted(t, T, side='right') - 1, 0), len(F) - 2))
        if abs(t[k] - T) < 1e-6 or mode == 'uniform':
            img = F[min(i, len(F) - 1)] if mode == 'uniform' else F[k]
        else:
            al = (T - t[k]) / (t[k + 1] - t[k])
            src, frac, key = (F[k + 1], 1 - al, (k + 1, k)) if al >= 0.5 else (F[k], al, (k, k + 1))
            if key not in cache:
                fl = cv2.calcOpticalFlowFarneback(small(F[key[0]]), small(F[key[1]]), None, 0.5, 4, 25, 3, 7, 1.5, 0)
                cache = {key: cv2.resize(fl, (W, H)) * 2.0}
            fl = cache[key]; frac = np.float32(frac)
            img = cv2.remap(src, gx - frac * fl[..., 0], gy - frac * fl[..., 1], cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        out_frames.append(img)
        enc.stdin.write(np.ascontiguousarray(img).tobytes())
    enc.stdin.close(); enc.wait()
    print(f'judder before {unevenness(st[:a.frames]):.3f}  after {unevenness(steps(out_frames)):.3f}  -> {a.out}')


if __name__ == '__main__':
    main()
