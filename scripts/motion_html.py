"""Motion graphics in pure code: an HTML page that draws every frame from time (window.seek(t)), rendered with
Playwright + ffmpeg. Deterministic, sub-frame motion blur on a 180 degree shutter, never blurred across a cut.
Idea and render hygiene adapted from howseen-ai/claude-motion-design (MIT).

  python motion_html.py render PAGE.html OUT.mp4 --dur 6 [--fps 25] [--size 1920x1080] [--sub auto|1|4|8]
                        [--params '{"title": "Tuyến cao tốc"}'] [--cuts 2.0,4.5] [--draft]
  python motion_html.py stills PAGE.html sheet.png --times 0.5 1.5 3 5 [--size ...] [--params ...]   # look before rendering

PAGE contract (see templates/motion/*.html):
  window.PARAMS     is set before load from --params (read it to fill text/numbers)
  window.seek(t)    async; draws the frame for time t (seconds). No CSS transitions, no timers, no Math.random.
  window.ready=true after fonts/images are loaded.  window.DURATION (optional) suggested length.
Sub-frames: auto = measure motion between probe frames, 1 when still, 4 for slow, 8 for fast moves.
"""
import argparse, json, os, shutil, subprocess, sys, tempfile
import numpy as np


def _page(pw, html, W, H, params, scale=1):
    br = pw.chromium.launch(args=['--force-color-profile=srgb', '--font-render-hinting=none', '--disable-threaded-animation',
                                  '--run-all-compositor-stages-before-draw', '--enable-unsafe-swiftshader', '--use-angle=swiftshader'])
    pg = br.new_page(viewport={'width': W, 'height': H}, device_scale_factor=scale)
    pg.add_init_script(f'window.PARAMS = {json.dumps(params or {}, ensure_ascii=False)};')
    pg.goto('file:///' + os.path.abspath(html).replace('\\', '/'))
    pg.wait_for_function('window.ready === true', timeout=30000)
    pg.evaluate('document.fonts.ready.then(()=>{document.getAnimations().forEach(a=>a.pause())})')
    return br, pg


def _shot(pg, t):
    pg.evaluate(f'window.seek({t:.6f})')
    pg.evaluate('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
    return pg.screenshot(type='png')


def _arr(png):
    import cv2
    return cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)


def stills(html, out, times, W, H, params):
    import cv2
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        br, pg = _page(pw, html, W, H, params)
        ims = [cv2.resize(_arr(_shot(pg, t)), (480, int(480 * H / W))) for t in times]
        br.close()
    for im, t in zip(ims, times): cv2.putText(im, f'{t:.2f}s', (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    cols = 4; rows = [np.hstack(ims[i:i + cols] + [np.zeros_like(ims[0])] * (cols - len(ims[i:i + cols]))) for i in range(0, len(ims), cols)]
    cv2.imwrite(out, np.vstack(rows)); print('stills ->', out)


def render(html, out, dur, fps=25, W=1920, H=1080, sub='auto', params=None, cuts=(), draft=False):
    from playwright.sync_api import sync_playwright
    if os.path.exists(out): raise SystemExit(f'{out} đã tồn tại')
    if draft: W, H, fps, sub = W // 2, H // 2, min(fps, 25), '1'
    n = int(round(dur * fps)); shutter = 0.5
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(fps), '-i', '-',
                            '-vf', 'scale=in_range=pc:out_range=tv:out_color_matrix=bt709,format=yuv420p', '-color_range', 'tv',
                            '-colorspace', 'bt709', '-c:v', 'libx264', '-crf', '23' if draft else '14', '-preset', 'veryfast' if draft else 'slow',
                            '-movflags', '+faststart', out], stdin=subprocess.PIPE)
    with sync_playwright() as pw:
        br, pg = _page(pw, html, W, H, params)
        prev = None; used = []
        for k in range(n):
            t = k / fps
            a = _arr(_shot(pg, t))
            if sub == 'auto':
                m = 0 if prev is None else float(np.abs(a.astype(np.int16) - prev).mean())
                ns = 1 if m < 0.6 else (4 if m < 6 else 8)
            else:
                ns = int(sub)
            near_cut = any(abs(t - c) < 1.0 / fps for c in cuts)
            if ns > 1 and not near_cut:
                acc = a.astype(np.float32)
                for j in range(1, ns):                       # spread over half the frame interval (180 deg shutter)
                    acc += _arr(_shot(pg, t + shutter / fps * j / ns)).astype(np.float32)
                fr = (acc / ns).astype(np.uint8)
            else:
                fr = a
            prev = a; used.append(ns)
            enc.stdin.write(np.ascontiguousarray(fr).tobytes())
        br.close()
    enc.stdin.close(); enc.wait()
    print(f'{out}: {n} frames {W}x{H}@{fps}, subframes avg {np.mean(used):.1f}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    r = sp.add_parser('render'); r.add_argument('html'); r.add_argument('out'); r.add_argument('--dur', type=float, required=True)
    r.add_argument('--fps', type=float, default=25); r.add_argument('--size', default='1920x1080'); r.add_argument('--sub', default='auto')
    r.add_argument('--params', default='{}'); r.add_argument('--cuts', default=''); r.add_argument('--draft', action='store_true')
    s = sp.add_parser('stills'); s.add_argument('html'); s.add_argument('out'); s.add_argument('--times', type=float, nargs='+', required=True)
    s.add_argument('--size', default='1920x1080'); s.add_argument('--params', default='{}')
    a = ap.parse_args()
    W, H = map(int, a.size.split('x')); params = json.loads(a.params)
    if a.cmd == 'stills': stills(a.html, a.out, a.times, W, H, params)
    else: render(a.html, a.out, a.dur, a.fps, W, H, a.sub, params, [float(x) for x in a.cuts.split(',') if x], a.draft)


if __name__ == '__main__':
    main()
