"""Footage library: split every file into shots, score them, search them, pick the best.

  python shot_select.py scan  FOLDER_OR_FILES... --out lib.json [--sheet lib_sheet.jpg] [--clip]
  python shot_select.py best  lib.json [--min-dur 3] [--top 20] [--moving|--static]
  python shot_select.py search lib.json "cable-stayed bridge aerial at sunset" [--top 8]     (needs --clip at scan)

Per shot: start/end, fps, sharpness (Laplacian variance, 0..1 normalised), exposure (mean, % clipped), camera
motion (global pan speed px/s at 1080p), smoothness (judder 0 = even), shake (high-frequency jitter), faces,
score 0..100. Shots inside a file never cross a cut (cut +2 / -3 frame margins).
CLIP (openai/clip-vit-base-patch32, safetensors, ~600 MB, downloaded once) embeds 3 frames per shot so you can search
by English description; translate Vietnamese queries first.
"""
import argparse, glob, json, os, subprocess, sys
import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
YUNET = os.environ.get('YUNET_ONNX', os.path.expanduser('~/tools/models/face_detection_yunet_2023mar.onnx'))
EXT = ('.mp4', '.mov', '.mkv', '.mxf', '.avi', '.m4v', '.mts')


def probe(p):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,avg_frame_rate:format=duration',
                        '-of', 'csv=p=0', p], capture_output=True, text=True).stdout.split()
    w, h, fr = r[0].split(',')[:3]; a, b = fr.split('/')
    return int(w), int(h), float(a) / float(b), float(r[-1])


def frames(p, W=320):
    w, h, fps, d = probe(p); H = int(round(h * W / w / 2)) * 2
    pr = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', p, '-an', '-vf', f'scale={W}:{H}', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'],
                          stdout=subprocess.PIPE)
    sz = W * H * 3
    while True:
        b = pr.stdout.read(sz)
        if len(b) < sz: break
        yield np.frombuffer(b, np.uint8).reshape(H, W, 3)
    pr.wait()


def judder(st):
    k = 5
    if len(st) < 2 * k + 6: return None
    tr = np.convolve(st, np.ones(k) / k, 'same'); m = tr[k:-k] > 0.4
    if m.sum() < 8: return None
    return float(np.mean(np.abs(st[k:-k][m] - tr[k:-k][m])) / (np.mean(tr[k:-k][m]) + 1e-6))


def scan_file(p, det=None):
    w, h, fps, dur = probe(p)
    G, sharp, lum, clip, fc, dxy, keep = [], [], [], [], [], [], []
    prev = None
    for k, f in enumerate(frames(p)):
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32)
        G.append(cv2.resize(g, (96, 54)).mean())
        sharp.append(cv2.Laplacian(g, cv2.CV_32F).var()); lum.append(g.mean()); clip.append(float(((g > 250) | (g < 5)).mean()))
        if det is not None and k % 6 == 0:
            det.setInputSize((f.shape[1], f.shape[0])); _, fa = det.detect(f); fc.append(0 if fa is None else len(fa))
        if prev is not None:
            (dx, dy), _ = cv2.phaseCorrelate(prev, g); dxy.append((dx, dy))
        else:
            dxy.append((0.0, 0.0))
        prev = g
        if k % max(1, int(fps)) == 0: keep.append(k)
    n = len(sharp)
    # cuts from small-frame differences
    small = list(frames(p, 96)); d = [np.abs(small[i].astype(np.float32) - small[i - 1]).mean() for i in range(1, len(small))]
    med = float(np.median(d)) if d else 0
    cuts = [i + 1 for i, v in enumerate(d) if v > 28 and v > 6 * med + 4]
    b = [0] + cuts + [n]; shots = []
    sc = 1080 / (320 * h / w)                     # analysis pixels -> pixels at 1080p
    for a, e in zip(b, b[1:]):
        a2, e2 = a + (2 if a else 0), e - (3 if e < n else 0)
        if e2 - a2 < int(fps * 1.0): continue
        mv = np.array(dxy[a2 + 1:e2]); spd = np.hypot(mv[:, 0], mv[:, 1]) * sc if len(mv) else np.zeros(1)
        kk = max(3, int(fps * 0.5) | 1)
        smth = np.stack([np.convolve(mv[:, i], np.ones(kk) / kk, 'same') for i in range(2)], 1) if len(mv) > kk else mv
        shake = float(np.mean(np.hypot(*(mv - smth).T)) * sc) if len(mv) > kk else 0.0
        j = judder(spd)
        shp = float(np.median(sharp[a2:e2])); ex = float(np.mean(lum[a2:e2])); cl = float(np.mean(clip[a2:e2]))
        faces = int(np.max(fc[a2 // 6:max(a2 // 6 + 1, e2 // 6)])) if fc else 0
        shots.append({'file': p, 'start': round(a2 / fps, 3), 'end': round(e2 / fps, 3), 'dur': round((e2 - a2) / fps, 2), 'fps': round(fps, 3),
                      'res': f'{w}x{h}', 'sharp_raw': round(shp, 1), 'exposure': round(ex, 1), 'clipped': round(cl, 3),
                      'motion_px_s': round(float(np.median(spd)) * fps, 1), 'judder': None if j is None else round(j, 3),
                      'shake_px': round(shake, 2), 'faces': faces})
    return shots


def score(lib):
    sh = np.array([s['sharp_raw'] for s in lib]) if lib else np.zeros(1)
    lo, hi = np.percentile(sh, 5), np.percentile(sh, 95)
    for s in lib:
        s['sharp'] = round(float(np.clip((s['sharp_raw'] - lo) / (hi - lo + 1e-6), 0, 1)), 3)
        ex = 1 - min(1, abs(s['exposure'] - 118) / 90); cl = 1 - min(1, s['clipped'] * 8)
        sm = 1.0 if s['judder'] is None else max(0, 1 - s['judder'] / 0.6)
        st = max(0, 1 - s['shake_px'] / 6); res = min(1, int(s['res'].split('x')[1]) / 1080)
        ln = min(1, s['dur'] / 4)
        s['score'] = round(100 * (0.25 * s['sharp'] + 0.15 * ex + 0.1 * cl + 0.2 * sm + 0.15 * st + 0.1 * res + 0.05 * ln), 1)
    return lib


def _feat(m, out, kind):
    """transformers 4 returns a tensor; transformers 5 may return a ModelOutput -> project the pooled output."""
    import torch
    if isinstance(out, torch.Tensor): return out
    for k in ('image_embeds', 'text_embeds'):
        if getattr(out, k, None) is not None: return getattr(out, k)
    pooled = out.pooler_output
    proj = m.visual_projection if kind == 'image' else m.text_projection
    return proj(pooled) if pooled.shape[-1] != proj.out_features else pooled


def clip_embed(lib):
    import torch
    from transformers import CLIPModel, CLIPProcessor
    name = 'openai/clip-vit-base-patch32'
    m = CLIPModel.from_pretrained(name, use_safetensors=True).eval(); pr = CLIPProcessor.from_pretrained(name)
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'; m.to(dev)
    for s in lib:
        ims = []
        for t in (s['start'] + 0.3, (s['start'] + s['end']) / 2, s['end'] - 0.3):
            r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.2f}', '-i', s['file'], '-frames:v', '1', '-vf', 'scale=336:-2',
                                '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True)
            im = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)
            if im is not None: ims.append(cv2.cvtColor(im, cv2.COLOR_BGR2RGB))
        if not ims: continue
        with torch.no_grad():
            e = _feat(m, m.get_image_features(**pr(images=ims, return_tensors='pt').to(dev)), 'image')
        e = torch.nn.functional.normalize(e, dim=-1).mean(0); s['clip'] = torch.nn.functional.normalize(e, dim=0).cpu().tolist()
    return lib


def search(lib, query, top=8):
    import torch
    from transformers import CLIPModel, CLIPProcessor
    name = 'openai/clip-vit-base-patch32'
    m = CLIPModel.from_pretrained(name, use_safetensors=True).eval(); pr = CLIPProcessor.from_pretrained(name)
    with torch.no_grad():
        q = torch.nn.functional.normalize(_feat(m, m.get_text_features(**pr(text=[query], return_tensors='pt', padding=True)), 'text'), dim=-1)[0].numpy()
    res = [(float(np.dot(q, np.array(s['clip']))), s) for s in lib if s.get('clip')]
    res.sort(key=lambda x: -x[0])
    return [dict(s, match=round(c, 3)) for c, s in res[:top]]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    s = sp.add_parser('scan'); s.add_argument('inputs', nargs='+'); s.add_argument('--out', required=True); s.add_argument('--clip', action='store_true')
    s.add_argument('--sheet')
    b = sp.add_parser('best'); b.add_argument('lib'); b.add_argument('--min-dur', type=float, default=3); b.add_argument('--top', type=int, default=20)
    b.add_argument('--moving', action='store_true'); b.add_argument('--static', action='store_true')
    q = sp.add_parser('search'); q.add_argument('lib'); q.add_argument('query'); q.add_argument('--top', type=int, default=8)
    a = ap.parse_args()
    if a.cmd == 'scan':
        files = []
        for x in a.inputs:
            files += [os.path.join(r, f) for r, _, fs in os.walk(x) for f in fs if f.lower().endswith(EXT)] if os.path.isdir(x) else [x]
        det = cv2.FaceDetectorYN.create(YUNET, '', (320, 180), 0.75, 0.3, 50) if os.path.exists(YUNET) else None
        lib = []
        for f in files:
            sh = scan_file(f, det); lib += sh; print(f'{len(sh):3d} shots  {f}')
        lib = score(lib)
        if a.clip: lib = clip_embed(lib)
        json.dump(lib, open(a.out, 'w', encoding='utf8'), ensure_ascii=False)
        print(f'{len(lib)} shots -> {a.out}')
        if a.sheet:
            rows = []
            for i, s in enumerate(sorted(lib, key=lambda s: -s['score'])[:60]):
                r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{(s["start"] + s["end"]) / 2:.2f}', '-i', s['file'], '-frames:v', '1',
                                    '-vf', 'scale=320:180', '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True)
                im = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)
                if im is None: continue
                cv2.putText(im, f'#{i} {s["score"]:.0f} {s["dur"]:.1f}s', (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                rows.append(im)
            while len(rows) % 6: rows.append(np.zeros_like(rows[0]))
            cv2.imwrite(a.sheet, np.vstack([np.hstack(rows[i:i + 6]) for i in range(0, len(rows), 6)]))
            print('sheet ->', a.sheet)
    elif a.cmd == 'best':
        lib = json.load(open(a.lib, encoding='utf8'))
        c = [s for s in lib if s['dur'] >= a.min_dur and (not a.moving or s['motion_px_s'] > 20) and (not a.static or s['motion_px_s'] <= 20)]
        for s in sorted(c, key=lambda s: -s['score'])[:a.top]:
            print(f"{s['score']:5.1f}  {os.path.basename(s['file'])} {s['start']:.2f}-{s['end']:.2f} ({s['dur']}s) sharp {s['sharp']} "
                  f"judder {s['judder']} shake {s['shake_px']} motion {s['motion_px_s']}px/s faces {s['faces']}")
    else:
        for s in search(json.load(open(a.lib, encoding='utf8')), a.query, a.top):
            print(f"{s['match']:.3f}  score {s['score']:5.1f}  {os.path.basename(s['file'])} {s['start']:.2f}-{s['end']:.2f}")


if __name__ == '__main__':
    main()
