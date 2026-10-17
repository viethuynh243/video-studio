"""Virtual camera: automatic reframing, virtual camera moves, stabilisation.

  python camera.py reframe SRC.mp4 OUT.mp4 --aspect 9:16 [--size 1080x1920] [--max-pan 0.25] [--mode auto|static|follow]
      AutoFlip-style smart crop (16:9 -> 9:16 / 1:1 / 4:5, or punch-in inside a 4K frame). Importance map per frame =
      faces (YuNet) + spectral-residual saliency + motion. Per shot (cuts detected) it behaves like a camera operator:
      subject barely moves -> locked-off crop (tripod); otherwise a smoothed pan with a speed limit
      (--max-pan = fraction of the frame width per second) and eased starts/stops. Never pans across a cut.

  python camera.py move SRC.mp4 OUT.mp4 --move push_in|pull_out|pan_left|pan_right|tilt_up|tilt_down|orbit_drift
                        [--amount 0.10] [--start 0 --dur 5] [--size 1920x1080] [--ease smoother]
      Sub-pixel virtual camera move inside the frame (best from 4K sources delivered at 1080p: no quality loss).

  python camera.py stabilize SRC.mp4 OUT.mp4 [--strength 30] [--tripod]
      Two-pass vidstab (libvidstab). --tripod locks the frame completely (for "static camera" shots, AI clips).
"""
import argparse, os, re, subprocess, sys
import numpy as np
import cv2

YUNET = os.environ.get('YUNET_ONNX', os.path.expanduser('~/tools/models/face_detection_yunet_2023mar.onnx'))


def info(src):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,avg_frame_rate',
                        '-of', 'csv=p=0', src], capture_output=True, text=True).stdout.strip().split(',')
    a, b = r[2].split('/'); return int(r[0]), int(r[1]), float(a) / float(b)


def reader(src, w=None, h=None, start=None, dur=None, gray=False):
    W, H, _ = info(src); w, h = w or W, h or H
    cmd = ['ffmpeg', '-v', 'error'] + (['-ss', str(start)] if start is not None else []) + (['-t', str(dur)] if dur else []) + \
          ['-i', src, '-an', '-vf', f'scale={w}:{h}', '-f', 'rawvideo', '-pix_fmt', 'gray' if gray else 'bgr24', '-']
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE); c = 1 if gray else 3; sz = w * h * c
    while True:
        b = p.stdout.read(sz)
        if len(b) < sz: break
        yield np.frombuffer(b, np.uint8).reshape(h, w) if gray else np.frombuffer(b, np.uint8).reshape(h, w, 3)
    p.wait()


def writer(out, W, H, fps, crf=16):
    return subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(fps), '-i', '-',
                             '-c:v', 'libx264', '-crf', str(crf), '-preset', 'slow', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out],
                            stdin=subprocess.PIPE)


def saliency(g):
    """Spectral residual saliency (Hou & Zhang 2007) on a small gray frame."""
    s = cv2.resize(g, (64, 64)).astype(np.float32)
    F = np.fft.fft2(s); la = np.log(np.abs(F) + 1e-6); ph = np.angle(F)
    sr = la - cv2.blur(la, (3, 3))
    m = np.abs(np.fft.ifft2(np.exp(sr + 1j * ph))) ** 2
    m = cv2.GaussianBlur(m, (9, 9), 2.5); m = cv2.resize(m, (g.shape[1], g.shape[0]))
    return m / (m.max() + 1e-9)


def analyse(src, aw=480):
    W, H, fps = info(src); ah = int(round(H * aw / W / 2)) * 2
    det = None; fw = min(W, 1280); fh = int(round(H * fw / W))
    if os.path.exists(YUNET):
        det = cv2.FaceDetectorYN.create(YUNET, '', (fw, fh), 0.75, 0.3, 50)
    cx, cy, cuts, prev, held, age = [], [], [0], None, [], 99
    for k, f in enumerate(reader(src, fw, fh)):
        f_s = cv2.resize(f, (aw, ah), interpolation=cv2.INTER_AREA)
        g = cv2.cvtColor(f_s, cv2.COLOR_BGR2GRAY)
        imp = saliency(g) * 0.5
        if prev is not None:
            dif = cv2.absdiff(g, prev).astype(np.float32)
            if dif.mean() > 28: cuts.append(k); held, age = [], 99
            imp += 0.3 * cv2.GaussianBlur(dif, (21, 21), 0) / (dif.max() + 1e-6)
        prev = g
        if det is not None and k % 2 == 0:            # faces at higher resolution (small faces in wide shots)
            _, faces = det.detect(f)
            faces = [fa for fa in (faces if faces is not None else []) if fa[3] >= fh * 0.03]   # drop tiny false faces
            if faces: held, age = [fa[:4] * (aw / fw) for fa in faces], 0
        age += 1
        if held and age < 12:                         # keep the last faces for a moment (blinks, turned heads)
            for x, y, w, h in held:
                x0, y0 = max(0, int(x - w * 0.6)), max(0, int(y - h * 0.3))
                imp[y0:int(y + h * 3.0), x0:int(x + w * 1.6)] += 1.5          # head + upper body
                imp[max(0, int(y)):int(y + h), max(0, int(x)):int(x + w)] += 4.0   # faces dominate
        imp = imp ** 2
        ys, xs = np.mgrid[0:ah, 0:aw]; t = imp.sum() + 1e-9
        gx, gy = float((imp * xs).sum() / t) / aw, float((imp * ys).sum() / t) / ah
        if held and age < 12:      # people first: centre on the faces (largest weighted), keep 30 % of the scene centroid
            ws = np.array([w * h for _, _, w, h in held]); fx = np.array([(x + w / 2) / aw for x, _, w, _ in held])
            fy = np.array([(y + h * 1.2) / ah for _, y, _, h in held])        # a little below the eyes = headroom
            gx = 0.7 * float((fx * ws).sum() / ws.sum()) + 0.3 * gx; gy = 0.7 * float((fy * ws).sum() / ws.sum()) + 0.3 * gy
        cx.append(gx); cy.append(gy)
    return np.array(cx), np.array(cy), cuts + [len(cx)], (W, H, fps)


def smooth_path(x, fps, half, max_pan, mode):
    """x: desired crop centre (0..1) per frame for one shot. Returns a camera-like path."""
    lo, hi = half, 1 - half
    x = np.clip(x, lo, hi)
    if len(x) < 3: return x
    spread = np.percentile(x, 90) - np.percentile(x, 10)
    if mode == 'static' or (mode == 'auto' and spread < half * 0.35):
        return np.full_like(x, np.clip(np.median(x), lo, hi))          # locked-off
    k = max(3, int(fps * 0.8) | 1)
    xs = np.convolve(np.pad(x, k, mode='edge'), np.hanning(k * 2 + 1) / np.hanning(k * 2 + 1).sum(), 'same')[k:-k]
    v = max_pan / fps; out = [xs[0]]
    for t in xs[1:]:
        out.append(out[-1] + np.clip(t - out[-1], -v, v))                 # speed limit like a fluid head
    out = np.array(out)
    k2 = max(3, int(fps * 0.4) | 1)
    out = np.convolve(np.pad(out, k2, mode='edge'), np.ones(k2) / k2, 'same')[k2:-k2]   # ease accelerations
    return np.clip(out, lo, hi)


def reframe(src, out, aspect='9:16', size=None, max_pan=0.25, mode='auto'):
    cx, cy, cuts, (W, H, fps) = analyse(src)
    an, ad = map(float, aspect.split(':')); ta = an / ad
    if W / H > ta: cw, ch = int(round(H * ta / 2)) * 2, H
    else: cw, ch = W, int(round(W / ta / 2)) * 2
    ow, oh = map(int, size.split('x')) if size else (cw, ch)
    px = np.zeros(len(cx)); py = np.zeros(len(cy))
    for a, b in zip(cuts, cuts[1:]):
        if b <= a: continue
        px[a:b] = smooth_path(cx[a:b], fps, cw / W / 2, max_pan, mode)
        py[a:b] = smooth_path(cy[a:b], fps, ch / H / 2, max_pan, mode)
    enc = writer(out, ow, oh, fps)
    for k, f in enumerate(reader(src)):
        if k >= len(px): break
        x0 = int(round(px[k] * W - cw / 2)); y0 = int(round(py[k] * H - ch / 2))
        x0 = min(max(0, x0), W - cw); y0 = min(max(0, y0), H - ch)
        crop = f[y0:y0 + ch, x0:x0 + cw]
        if (cw, ch) != (ow, oh): crop = cv2.resize(crop, (ow, oh), interpolation=cv2.INTER_AREA if ow < cw else cv2.INTER_LANCZOS4)
        enc.stdin.write(np.ascontiguousarray(crop).tobytes())
    enc.stdin.close(); enc.wait()
    print(f'reframe {W}x{H} -> crop {cw}x{ch} -> {ow}x{oh}, {len(cuts) - 1} shot(s), mode {mode}')


EASE = {'linear': lambda p: p, 'smooth': lambda p: p * p * (3 - 2 * p), 'smoother': lambda p: p ** 3 * (p * (6 * p - 15) + 10)}


def move(src, out, kind='push_in', amount=0.10, start=None, dur=None, size='1920x1080', ease='smoother'):
    W, H, fps = info(src); ow, oh = map(int, size.split('x'))
    frames = list(reader(src, start=start, dur=dur)); n = len(frames); e = EASE[ease]
    base = max(ow / W, oh / H)
    enc = writer(out, ow, oh, fps)
    for k, f in enumerate(frames):
        p = e(k / max(1, n - 1))
        z, dx, dy = 1.0 + amount, 0.0, 0.0
        if kind == 'push_in': z = 1.0 + amount * p
        elif kind == 'pull_out': z = 1.0 + amount * (1 - p)
        elif kind == 'pan_left': dx = amount * (0.5 - p)
        elif kind == 'pan_right': dx = amount * (p - 0.5)
        elif kind == 'tilt_up': dy = amount * (0.5 - p)
        elif kind == 'tilt_down': dy = amount * (p - 0.5)
        elif kind == 'orbit_drift': z = 1.0 + amount * 0.6 * p; dx = amount * 0.5 * (p - 0.5)
        s = base * z; cx = W / 2 + dx * W / z; cy = H / 2 + dy * H / z
        M = np.float32([[s, 0, ow / 2 - s * cx], [0, s, oh / 2 - s * cy]])
        enc.stdin.write(cv2.warpAffine(f, M, (ow, oh), flags=cv2.INTER_LANCZOS4 if s > 1 else cv2.INTER_AREA,
                                       borderMode=cv2.BORDER_REFLECT).tobytes())
    enc.stdin.close(); enc.wait()
    print(f'move {kind} {amount:+.0%} over {n} frames ({ease}) -> {out}')


def stabilize(src, out, strength=30, tripod=False):
    trf = os.path.splitext(out)[0] + '.trf'
    d = os.path.dirname(os.path.abspath(out)); tf = os.path.basename(trf)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.abspath(src), '-vf',
                    f'vidstabdetect=shakiness=6:accuracy=15:result={tf}' + (':tripod=1' if tripod else ''), '-f', 'null', '-'], cwd=d, check=True)
    vf = f'vidstabtransform=input={tf}:smoothing={strength}:optzoom=1:interpol=bicubic' + (':tripod=1' if tripod else '') + ',unsharp=5:5:0.5:3:3:0.3'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.abspath(src), '-vf', vf, '-c:v', 'libx264', '-crf', '16', '-preset', 'slow',
                    '-pix_fmt', 'yuv420p', '-c:a', 'copy', os.path.abspath(out)], cwd=d, check=True)
    os.remove(trf); print('stabilized ->', out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    r = sp.add_parser('reframe'); r.add_argument('src'); r.add_argument('out'); r.add_argument('--aspect', default='9:16')
    r.add_argument('--size'); r.add_argument('--max-pan', type=float, default=0.25); r.add_argument('--mode', default='auto')
    m = sp.add_parser('move'); m.add_argument('src'); m.add_argument('out'); m.add_argument('--move', default='push_in')
    m.add_argument('--amount', type=float, default=0.10); m.add_argument('--start', type=float); m.add_argument('--dur', type=float)
    m.add_argument('--size', default='1920x1080'); m.add_argument('--ease', default='smoother')
    s = sp.add_parser('stabilize'); s.add_argument('src'); s.add_argument('out'); s.add_argument('--strength', type=int, default=30)
    s.add_argument('--tripod', action='store_true')
    a = ap.parse_args()
    for o in [a.out]:
        if os.path.exists(o): raise SystemExit(f'{o} đã tồn tại')
    if a.cmd == 'reframe': reframe(a.src, a.out, a.aspect, a.size, a.max_pan, a.mode)
    elif a.cmd == 'move': move(a.src, a.out, a.move, a.amount, a.start, a.dur, a.size, a.ease)
    else: stabilize(a.src, a.out, a.strength, a.tripod)


if __name__ == '__main__':
    main()
