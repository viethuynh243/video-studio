"""Colour: shot matching, auto balance, looks - all as 3D LUTs (.cube) so ffmpeg applies them fast and exactly.

  python grade.py match  REF(.jpg|.mp4@sec) SRC.mp4 OUT.cube [--strength 0.8]   # make SRC look like REF (Lab statistics)
  python grade.py auto   SRC.mp4 OUT.cube [--strength 0.7]                       # neutral white balance + exposure
  python grade.py look   OUT.cube --look filmic|teal_orange|warm|cool|bw|clean [--strength 1]
  python grade.py apply  SRC.mp4 LUT.cube OUT.mp4 [--lut2 LUT.cube]              # apply (chain up to 2 LUTs)

Importable: lut_match(ref_frames, src_frames), lut_auto(src_frames), lut_look(name), write_cube(lut, path),
sample_frames(path, n). Matching follows Reinhard et al. colour transfer in Lab, blended by --strength.
"""
import argparse, os, subprocess
import numpy as np
import cv2

N = 33


def sample_frames(spec, n=6):
    """'file.jpg' | 'video.mp4' (n frames spread) | 'video.mp4@12.5' (one frame)."""
    if spec.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.webp')):
        return [cv2.imdecode(np.fromfile(spec, np.uint8), cv2.IMREAD_COLOR)]
    path, at = (spec.rsplit('@', 1) + [None])[:2] if '@' in spec else (spec, None)
    d = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path],
                             capture_output=True, text=True).stdout)
    ts = [float(at)] if at else [d * (i + 0.5) / n for i in range(n)]
    out = []
    for t in ts:
        r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.3f}', '-i', path, '-frames:v', '1', '-vf', 'scale=480:-2',
                            '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True)
        im = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)
        if im is not None: out.append(im)
    return out


def grid():
    v = np.linspace(0, 1, N, dtype=np.float32)
    b, g, r = np.meshgrid(v, v, v, indexing='ij')          # .cube order: R fastest, then G, then B
    return np.stack([r, g, b], -1).reshape(-1, 3)        # RGB 0..1


def lab_stats(frames):
    px = np.concatenate([cv2.cvtColor(f.astype(np.float32) / 255, cv2.COLOR_BGR2Lab).reshape(-1, 3) for f in frames])
    lo, hi = np.percentile(px[:, 0], 2), np.percentile(px[:, 0], 98)
    px = px[(px[:, 0] > lo) & (px[:, 0] < hi)] if len(px) > 1000 else px          # ignore clipped extremes
    return px.mean(0), px.std(0) + 1e-3


def _apply_lab(rgb, fn, strength):
    bgr = rgb[:, ::-1].reshape(-1, 1, 3).astype(np.float32)
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2Lab).reshape(-1, 3)
    lab2 = lab + strength * (fn(lab) - lab)
    out = cv2.cvtColor(lab2.reshape(-1, 1, 3).astype(np.float32), cv2.COLOR_Lab2BGR).reshape(-1, 3)[:, ::-1]
    return np.clip(out, 0, 1)


def lut_match(ref, src, strength=0.8):
    mr, sr = lab_stats(ref); ms, ss = lab_stats(src)
    scale = np.clip(sr / ss, 0.6, 1.6)                    # keep it a correction, not a repaint
    return _apply_lab(grid(), lambda L: (L - ms) * scale + mr, strength)


def lut_auto(src, strength=0.7, target_L=52.0):
    m, s = lab_stats(src)
    def fn(L):
        o = L.copy(); o[:, 1] -= m[1]; o[:, 2] -= m[2]                     # neutral grey world on a/b
        o[:, 0] = (L[:, 0] - m[0]) * np.clip(18.0 / s[0], 0.85, 1.25) + target_L
        return o
    return _apply_lab(grid(), fn, strength)


def lut_look(name, strength=1.0):
    g = grid()
    r, gg, b = g[:, 0], g[:, 1], g[:, 2]; luma = 0.2126 * r + 0.7152 * gg + 0.0722 * b
    if name == 'clean':
        o = g.copy()
    elif name == 'filmic':
        curve = lambda x: np.clip(0.5 + (x - 0.5) * 1.08 - 0.06 * np.sin(2 * np.pi * x) * 0.5, 0, 1)
        o = np.stack([curve(r), curve(gg), curve(b)], 1); o = luma[:, None] + (o - luma[:, None]) * 0.92
        o[:, 0] += 0.012; o[:, 2] -= 0.008
    elif name == 'teal_orange':
        o = g.copy(); sh = np.clip(1 - luma * 1.6, 0, 1)[:, None]; hl = np.clip((luma - 0.45) * 1.6, 0, 1)[:, None]
        o += sh * np.array([-0.03, 0.01, 0.04]) + hl * np.array([0.04, 0.012, -0.03])
    elif name == 'warm':
        o = g + np.array([0.025, 0.008, -0.025])
    elif name == 'cool':
        o = g + np.array([-0.02, 0.0, 0.03])
    elif name == 'bw':
        o = np.repeat(np.clip(0.5 + (luma - 0.5) * 1.1, 0, 1)[:, None], 3, 1)
    else:
        raise SystemExit(f'look lạ: {name}')
    return np.clip(g + strength * (o - g), 0, 1)


def write_cube(lut, path, title='video-studio'):
    with open(path, 'w') as f:
        f.write(f'TITLE "{title}"\nLUT_3D_SIZE {N}\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n')
        for r, g, b in lut: f.write(f'{r:.6f} {g:.6f} {b:.6f}\n')


def apply(src, cubes, out):
    d = os.path.dirname(os.path.abspath(cubes[0]))
    vf = ','.join(f"lut3d=file='{os.path.basename(c)}':interp=tetrahedral" for c in cubes)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.abspath(src), '-vf', vf, '-c:v', 'libx264', '-crf', '16', '-preset', 'slow',
                    '-pix_fmt', 'yuv420p', '-c:a', 'copy', os.path.abspath(out)], cwd=d, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    m = sp.add_parser('match'); m.add_argument('ref'); m.add_argument('src'); m.add_argument('out'); m.add_argument('--strength', type=float, default=0.8)
    u = sp.add_parser('auto'); u.add_argument('src'); u.add_argument('out'); u.add_argument('--strength', type=float, default=0.7)
    l = sp.add_parser('look'); l.add_argument('out'); l.add_argument('--look', default='filmic'); l.add_argument('--strength', type=float, default=1.0)
    p = sp.add_parser('apply'); p.add_argument('src'); p.add_argument('lut'); p.add_argument('out'); p.add_argument('--lut2')
    a = ap.parse_args()
    if a.cmd == 'match': write_cube(lut_match(sample_frames(a.ref), sample_frames(a.src), a.strength), a.out)
    elif a.cmd == 'auto': write_cube(lut_auto(sample_frames(a.src), a.strength), a.out)
    elif a.cmd == 'look': write_cube(lut_look(a.look, a.strength), a.out)
    else:
        if os.path.exists(a.out): raise SystemExit(f'{a.out} đã tồn tại')
        apply(a.src, [a.lut] + ([a.lut2] if a.lut2 else []), a.out)
    print('ok ->', a.out)


if __name__ == '__main__':
    main()
