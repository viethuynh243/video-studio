"""Contact sheet: one row per shot, 3 frames (start+3f, middle, end-3f) with timecodes, for eye review.

  python contact_sheet.py FILM.mp4 sheet.jpg [--cols-per-page 6] [--thr 28]

Long films are split into several pages: sheet_p1.jpg, sheet_p2.jpg ...
"""
import argparse, os, subprocess, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from probe_qc import frames_small, cuts_of, probe


def grab(path, t, w=320):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{max(t, 0):.3f}', '-i', path, '-frames:v', '1', '-vf', f'scale={w}:-2',
                        '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True)
    im = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)
    return im if im is not None else np.zeros((w * 9 // 16, w, 3), np.uint8)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('film'); ap.add_argument('out'); ap.add_argument('--rows-per-page', type=int, default=12)
    ap.add_argument('--thr', type=float, default=28.0)
    a = ap.parse_args()
    fps = probe(a.film)['fps'] or 25.0
    fr = frames_small(a.film)
    _, cuts = cuts_of(fr, a.thr)
    b = [0] + cuts + [len(fr)]
    shots = [(x, y) for x, y in zip(b, b[1:]) if y > x]
    rows = []
    for k, (f0, f1) in enumerate(shots):
        ts = [(f0 + min(3, (f1 - f0) // 4)) / fps, (f0 + f1) / 2 / fps, (f1 - 1 - min(3, (f1 - f0) // 4)) / fps]
        ims = [grab(a.film, t) for t in ts]
        h = ims[0].shape[0]
        lab = np.full((h, 170, 3), 30, np.uint8)
        for j, txt in enumerate([f'#{k + 1}', f'{f0 / fps:.2f}s', f'-{f1 / fps:.2f}s', f'{(f1 - f0) / fps:.2f}s']):
            cv2.putText(lab, txt, (8, 30 + 30 * j), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        rows.append(np.hstack([lab] + [cv2.resize(i, (320, h)) for i in ims]))
    base, ext = os.path.splitext(a.out)
    pages = [rows[i:i + a.rows_per_page] for i in range(0, len(rows), a.rows_per_page)]
    for p, pr in enumerate(pages):
        name = a.out if len(pages) == 1 else f'{base}_p{p + 1}{ext}'
        cv2.imwrite(name, np.vstack(pr), [cv2.IMWRITE_JPEG_QUALITY, 85])
        print('wrote', name, len(pr), 'shots')


if __name__ == '__main__':
    main()
