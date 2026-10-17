"""Tự động tạo và chỉnh sửa video - một lệnh từ đầu đến cuối.

  python autovideo.py make    PROJECT.json [--out OUT.mp4]
      Dựng phim mới từ storyboard: cắt nguồn video (đúng fps, phủ khung), ảnh tĩnh Ken Burns mượt, chữ trên hình,
      hoà cảnh, giọng đọc TTS tiếng Việt (VieNeu), nhạc nền tự lặp + ducking, chuẩn LUFS, phụ đề burn-in + SRT,
      QC tự động và báo cáo. Mẫu: templates/project_make.json

  python autovideo.py revoice VIDEO.mp4 --script script.(json|txt) [--voice auto|"Tên giọng"|clone:mau.wav] [--muc-dich thoi_su] --out OUT.mp4
      Thay giọng thuyết minh của video có sẵn: tách giọng/nhạc (Demucs), tự dò mốc từng câu trên giọng cũ (Whisper)
      nếu kịch bản không có mốc, đọc lại bằng giọng mới, đặt đúng mốc, giữ nhạc gốc, QC + kiểm lời.

  python autovideo.py subs    VIDEO.mp4 --script script.(json|txt) --out OUT.mp4 [--from-audio]
      Phụ đề tự động: mốc lấy từ script.json hoặc tự dò trên tiếng của video; xuất SRT + burn-in.

  python autovideo.py qc      VIDEO.mp4 [--ref script.txt]

Chung: --work DIR (mặc định <out>_work), --capcut TEN_NHAP (đẩy thêm một bản nháp CapCut desktop),
--no-subs, --lufs -16, --slow 1.0. Không bao giờ ghi đè file đầu ra đã có.
script.txt = mỗi dòng một câu; script.json = ["câu", ...] hoặc [[start, end, "câu"], ...].
"""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import voice_mix, subs  # noqa: E402
from probe_qc import qc as run_qc, probe  # noqa: E402

FONT_BOLD = 'C:/Windows/Fonts/arialbd.ttf' if os.path.exists('C:/Windows/Fonts/arialbd.ttf') else 'NotoSans-Bold.ttf'


def log(*a):
    print(time.strftime('[%H:%M:%S]'), *a, flush=True)


def need_new(out):
    if os.path.exists(out): raise SystemExit(f'{out} đã tồn tại - đặt tên khác (không ghi đè bản giao)')


# ---------------------------------------------------------------- script / TTS
def read_script(p):
    if p.endswith('.json'):
        d = json.load(open(p, encoding='utf8'))
        if d and isinstance(d[0], str): return [(None, None, t) for t in d]
        return [(x['start'], x['end'], x['text']) if isinstance(x, dict) else (x[0], x[1], x[2]) for x in d]
    return [(None, None, l.strip()) for l in open(p, encoding='utf8') if l.strip()]


def ascii_name(v):
    import unicodedata
    v = v.replace('đ', 'd').replace('Đ', 'D')
    return ''.join(c for c in unicodedata.normalize('NFD', v) if unicodedata.category(c) != 'Mn' and c.isalnum())


def tts(texts, voice, outdir):
    """VieNeu TTS for a list of lines (cached by text+voice). Returns wav paths."""
    os.makedirs(outdir, exist_ok=True)
    key = hashlib.md5(json.dumps([voice, texts], ensure_ascii=False).encode()).hexdigest()[:10]
    tag = ascii_name(voice); files = [os.path.join(outdir, f'{tag}_{i}.wav') for i in range(len(texts))]
    stamp = os.path.join(outdir, f'{tag}.key')
    if all(map(os.path.exists, files)) and os.path.exists(stamp) and open(stamp).read() == key:
        return files
    jp = os.path.join(outdir, f'{tag}_lines.json'); json.dump(texts, open(jp, 'w', encoding='utf8'), ensure_ascii=False)
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    r = subprocess.run([sys.executable, os.path.join(HERE, 'tts_vi.py'), jp, outdir, '--voices', voice], env=env,
                       capture_output=True, text=True, encoding='utf8', errors='replace')
    if r.returncode or not all(map(os.path.exists, files)): raise RuntimeError('TTS lỗi:\n' + r.stdout[-600:] + r.stderr[-1200:])
    open(stamp, 'w').write(key)
    return files


def wav_dur(p):
    import soundfile as sf
    return sf.info(p).duration


# ---------------------------------------------------------------- alignment (script sentences -> times in audio)
def _fold(w):
    import unicodedata
    w = w.lower().replace('đ', 'd')
    return ''.join(c for c in unicodedata.normalize('NFD', w) if unicodedata.category(c) != 'Mn' and c.isalnum())


def align(audio, sentences, model='medium'):
    """Return [(start, end)] for each sentence, using Whisper word timestamps + sequence alignment on folded words."""
    import difflib
    from faster_whisper import WhisperModel
    m = WhisperModel(model, device='cpu', compute_type='int8')
    segs, _ = m.transcribe(audio, language='vi', word_timestamps=True, vad_filter=True, initial_prompt=' '.join(sentences)[:800])
    words = [w for s in segs for w in s.words]
    hyp = [_fold(w.word) for w in words]
    ref, owner = [], []
    for i, s in enumerate(sentences):
        for w in re.findall(r'\w+', s): ref.append(_fold(w)); owner.append(i)
    sm = difflib.SequenceMatcher(None, ref, hyp, autojunk=False)
    hit = [[] for _ in sentences]
    for a, b, n in sm.get_matching_blocks():
        for k in range(n): hit[owner[a + k]].append(words[b + k])
    out = []
    for i, h in enumerate(hit):
        out.append((h[0].start, h[-1].end) if h else (None, None))
    # interpolate sentences with no match
    for i, (s, e) in enumerate(out):
        if s is None:
            prev_e = next((out[j][1] for j in range(i - 1, -1, -1) if out[j][1] is not None), 0.0)
            nxt_s = next((out[j][0] for j in range(i + 1, len(out)) if out[j][0] is not None), prev_e + 3.0)
            out[i] = (prev_e + 0.2, max(prev_e + 0.5, nxt_s - 0.2))
    return out


def slots_from_times(times, total):
    """Speech times -> slots: each line may use the time until the next line starts (minus 0.15 s)."""
    sl = []
    for i, (s, e) in enumerate(times):
        nxt = times[i + 1][0] if i + 1 < len(times) else min(total, e + 3.0)
        sl.append((s, max(e, nxt - 0.15)))
    return sl


# ---------------------------------------------------------------- QC report
def report(out, work, ref_lines=None, extra=None, ignore=None):
    r = run_qc(out, True)
    s = r['summary']; i = r['info']
    inside = lambda f: any(a - 0.1 <= f.get('t', -9) <= b + 0.1 for a, b, _ in (ignore or []))
    planned = [f for f in r['findings'] if f['type'] != 'long_shot' and inside(f)]
    errs = [f for f in r['findings'] if f['type'] != 'long_shot' and not inside(f)]
    lines = [f'# Báo cáo QC - {os.path.basename(out)}', '',
             f'- {i["width"]}x{i["height"]}, {i["fps"]} fps, {i["duration"]:.2f} s, {i["nb_frames"]} khung',
             f'- Cắt cảnh: {s["cuts"]}, shot chuyển động: {s["moving_shots"]}, chỉ số giật trung vị {s["judder_median"]} (p90 {s["judder_p90"]})',
             f'- Âm lượng: {s.get("I_LUFS")} LUFS, True Peak {s.get("TP_dBFS")} dBFS, LRA {s.get("LRA")}',
             f'- Lỗi hình (khung lạc/chớp/khung lặp/đứng hình): {len(errs)}']
    for f in errs: lines.append(f'  - {f}')
    if planned:
        kinds = sorted({k for a, b, k in (ignore or []) if any(a - 0.1 <= f.get('t', -9) <= b + 0.1 for f in planned)})
        lines.append(f'- Thay đổi hình nằm trong chuyển cảnh/thẻ đã lên kế hoạch ({", ".join(kinds)}): {len(planned)} - không tính là lỗi')
    longs = [f for f in r['findings'] if f['type'] == 'long_shot']
    if longs: lines.append(f'- Shot dài > 8 s: {len(longs)} (kiểm có chủ ý không)')
    if extra: lines += [''] + extra
    p = os.path.join(work, 'BAO_CAO_QC.md'); open(p, 'w', encoding='utf8').write('\n'.join(lines) + '\n')
    log('QC:', f'{len(errs)} lỗi hình, {s.get("I_LUFS")} LUFS, giật trung vị {s["judder_median"]} ->', p)
    return r


def speech_accuracy(stem, texts):
    import difflib
    from faster_whisper import WhisperModel
    m = WhisperModel('medium', device='cpu', compute_type='int8')
    segs, _ = m.transcribe(stem, language='vi', vad_filter=True)
    hyp = ' '.join(s.text for s in segs)
    sp = os.path.join(HERE, 'speech_check.py')
    import importlib.util
    spec = importlib.util.spec_from_file_location('sc', sp); sc = importlib.util.module_from_spec(spec); spec.loader.exec_module(sc)
    ref = sc.spelled_to_digits(sc.tok(' '.join(texts))); h = sc.spelled_to_digits(sc.tok(hyp))
    smm = difflib.SequenceMatcher(None, ref, h, autojunk=False)
    acc = sum(n for *_, n in smm.get_matching_blocks()) / max(1, len(ref))
    errs = [(' '.join(ref[a1:a2]), ' '.join(h[b1:b2])) for op, a1, a2, b1, b2 in smm.get_opcodes() if op != 'equal']
    return acc, errs, hyp


def to_capcut(name, video_silent, voice_stem, music, srt, W, H):
    import capcut_api
    spec = {'name': name, 'width': W, 'height': H,
            'video': [{'file': os.path.abspath(video_silent), 'start': 0, 'end': probe(video_silent)['duration'], 'volume': 0}],
            'audio': [{'file': os.path.abspath(voice_stem), 'track': 'voice', 'volume': 1.0}]}
    if music: spec['audio'].append({'file': os.path.abspath(music), 'track': 'music', 'volume': 0.55})
    if srt: spec['srt'] = os.path.abspath(srt)
    sp = os.path.splitext(video_silent)[0] + '_capcut.json'
    json.dump(spec, open(sp, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    capcut_api.build(sp)


# ---------------------------------------------------------------- compositor (make)
def hex_bgr(h):
    h = h.lstrip('#'); return (int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16))


def safe_range(src, need_s, fps_src=None):
    """Keep a source piece inside ONE original shot. Detect hard cuts in [vao, ra (or vao+need+2)] and move to the
    continuous part (cut +2 frames ... next cut -3 frames) that fits need_s, preferring the earliest. Returns (vao, ra, note)."""
    vao = float(src.get('vao', 0)); ra = src.get('ra')
    end = float(ra) if ra is not None else vao + need_s + 2.0
    f = fps_src or probe(src['file'])['fps'] or 25.0
    r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{vao:.3f}', '-to', f'{end:.3f}', '-i', src['file'], '-an', '-vf',
                        'crop=iw:ih*0.78:0:0,scale=96:54,format=gray', '-f', 'rawvideo', '-'], capture_output=True)
    G = np.frombuffer(r.stdout, np.uint8).reshape(-1, 54, 96).astype(np.float32)
    if len(G) < 3: return vao, ra, ''
    d = np.abs(np.diff(G, axis=0)).mean((1, 2)); med = float(np.median(d))
    cuts = [i + 1 for i, v in enumerate(d) if v > 28 and v > 6 * med + 4]
    if not cuts: return vao, ra, ''
    b = [0] + cuts + [len(G)]
    segs = [(x + (2 if x else 0), y - (3 if y < len(G) else 0)) for x, y in zip(b, b[1:])]
    segs = [(x, y) for x, y in segs if y > x]
    need_f = int(np.ceil(need_s * f))
    ok = [s for s in segs if s[1] - s[0] >= need_f]
    best = ok[0] if ok else max(segs, key=lambda s: s[1] - s[0])
    a0, a1 = vao + best[0] / f, vao + best[1] / f
    note = f'nguồn có {len(cuts)} điểm cắt trong đoạn chọn -> dùng {a0:.2f}-{a1:.2f}s' + ('' if ok else ' (KHÔNG ĐỦ DÀI)')
    return a0, a1, note


def prepare_clip(c, n, W, H, fps, L, work):
    """Turn a source span into a clip at the project fps: frame-rate engine (RIFE / step+shutter / conform),
    slow motion, optional stabilisation, smart reframing when the aspect ratio differs. Cached by parameters."""
    import fps_convert, camera
    speed = float(c.get('toc_do', 1.0)); slowmo = float(c.get('slowmo', 1.0 / speed if speed != 1.0 else 1.0))
    out_s = L / fps
    key = hashlib.md5(json.dumps([n['file'], n.get('vao', 0), round(out_s, 3), fps, slowmo, c.get('on_dinh'), c.get('khung_thong_minh'), c.get('khung'),
                                  W, H, c.get('shutter', 180)]).encode()).hexdigest()[:12]
    d = os.path.join(work, 'clips'); os.makedirs(d, exist_ok=True)
    final = os.path.join(d, f'{key}.mp4')
    if os.path.exists(final): return final
    stage = os.path.join(d, f'{key}_a.mp4')
    fps_convert.convert(n['file'], stage, fps, start=float(n.get('vao', 0)), dur=out_s + 2.0 / fps, slowmo=slowmo,
                        shutter=float(c.get('shutter', 180)), crf=12, verbose=False)
    if c.get('on_dinh'):
        s2 = os.path.join(d, f'{key}_b.mp4'); camera.stabilize(stage, s2, tripod=c.get('on_dinh') == 'tripod'); stage = s2
    iw, ih, _ = camera.info(stage)
    mode = c.get('khung') or ('smart' if c.get('khung_thong_minh', True) else 'fill')
    differs = abs((iw / ih) - (W / H)) / (W / H) > 0.15
    if mode == 'smart' and differs:
        s3 = os.path.join(d, f'{key}_c.mp4'); camera.reframe(stage, s3, f'{W}:{H}', f'{W}x{H}'); stage = s3
    elif mode == 'fit_blur' and differs:
        s3 = os.path.join(d, f'{key}_c.mp4')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', stage, '-filter_complex',
                        f'[0]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},gblur=sigma=40,eq=brightness=-0.08[bg];'
                        f'[b]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2',
                        '-c:v', 'libx264', '-crf', '12', s3], check=True)
        stage = s3
    os.replace(stage, final)
    return final


def cam_warp(fr, k, n, spec):
    """Virtual camera move on an already framed W x H picture (subtle, eased)."""
    import cv2
    mv, amt = spec.get('move', 'push_in'), float(spec.get('amount', 0.08))
    p = k / max(1, n - 1); p = p ** 3 * (p * (6 * p - 15) + 10)
    z, dx, dy = 1.0 + amt, 0.0, 0.0
    if mv == 'push_in': z = 1.0 + amt * p
    elif mv == 'pull_out': z = 1.0 + amt * (1 - p)
    elif mv == 'pan_left': dx = amt * (0.5 - p) / 2
    elif mv == 'pan_right': dx = amt * (p - 0.5) / 2
    elif mv == 'tilt_up': dy = amt * (0.5 - p) / 2
    elif mv == 'tilt_down': dy = amt * (p - 0.5) / 2
    h, w = fr.shape[:2]; cx, cy = w / 2 + dx * w, h / 2 + dy * h
    M = np.float32([[z, 0, w / 2 - z * cx], [0, z, h / 2 - z * cy]])
    return cv2.warpAffine(fr, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)


def video_frames(src, W, H, fps, n, speed=1.0, vf_extra='', cwd=None):
    t0 = float(src.get('vao', 0))
    chain = [f'setpts=PTS/{speed}'] if speed != 1.0 else []
    if vf_extra: chain.append(vf_extra)
    chain += [f'fps={fps}', f'scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos', f'crop={W}:{H}', 'setsar=1']
    cmd = ['ffmpeg', '-v', 'error', '-ss', f'{t0:.3f}', '-i', src['file'], '-an', '-vf', ','.join(chain)]
    if src.get('ra') is not None: cmd[5:5] = ['-t', f'{(float(src["ra"]) - t0) / speed + 1.0 / fps:.3f}']
    p = subprocess.Popen(cmd + ['-frames:v', str(n), '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], stdout=subprocess.PIPE, cwd=cwd)
    sz, last, got = W * H * 3, None, 0
    while got < n:
        b = p.stdout.read(sz)
        if len(b) < sz: break
        last = np.frombuffer(b, np.uint8).reshape(H, W, 3); got += 1; yield last
    p.stdout.close(); p.wait()
    if got == 0:
        raise RuntimeError(f'không đọc được khung nào từ {src["file"]}@{t0}')
    if got < n:
        log(f'  CẢNH BÁO: nguồn {os.path.basename(src["file"])}@{t0} chỉ có {got}/{n} khung - giữ khung cuối {n - got} khung (nên chọn đoạn dài hơn)')
        for _ in range(n - got): yield last if last is not None else np.zeros((H, W, 3), np.uint8)


def image_frames(src, W, H, n):
    import cv2
    im = cv2.imdecode(np.fromfile(src['anh'], np.uint8), cv2.IMREAD_COLOR)
    if im is None: raise SystemExit(f'không đọc được ảnh {src["anh"]}')
    eff = src.get('hieu_ung', 'zoom_in')
    z0, z1 = {'zoom_in': (1.0, 1.08), 'zoom_out': (1.08, 1.0)}.get(eff, (1.04, 1.04))
    dx = {'pan_left': 0.03, 'pan_right': -0.03}.get(eff, 0.0)
    base = max(W / im.shape[1], H / im.shape[0])
    pre = min(1.0, base * 1.2)                       # pre-shrink big photos to limit aliasing
    if pre < 1.0: im = cv2.resize(im, None, fx=pre, fy=pre, interpolation=cv2.INTER_AREA); base /= pre
    ih, iw = im.shape[:2]
    for k in range(n):
        p = k / max(1, n - 1); p = p * p * (3 - 2 * p)                 # smoothstep
        s = base * (z0 + (z1 - z0) * p)
        cx, cy = iw / 2 + (dx * (p - 0.5)) * iw, ih / 2
        M = np.float32([[s, 0, W / 2 - s * cx], [0, s, H / 2 - s * cy]])
        yield cv2.warpAffine(im, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)


def color_card(bgr, W, H, n):
    """Solid card with a soft light that drifts slowly, so the frame is never dead (anti-AI-motion rule)."""
    ys, xs = np.mgrid[0:H // 4, 0:W // 4].astype(np.float32)
    base = np.zeros((H // 4, W // 4, 3), np.float32); base[:] = bgr
    import cv2
    for k in range(n):
        p = k / max(1, n - 1)
        cx, cy = (0.62 + 0.10 * p) * W / 4, (0.32 + 0.04 * np.sin(p * 3.1)) * H / 4
        g = np.exp(-(((xs - cx) / (W / 4 * 0.45)) ** 2 + ((ys - cy) / (H / 4 * 0.45)) ** 2))[..., None]
        light = 18 + 10 * (1 - abs(2 * p - 1))
        yield np.clip(cv2.resize(base + g * light, (W, H), interpolation=cv2.INTER_CUBIC), 0, 255).astype(np.uint8)


def text_layer(text, W, H, pos='top', lb=0):
    from PIL import Image, ImageDraw, ImageFont
    size = round(min(W, H) * (0.085 if pos == 'center' else 0.058)); f = ImageFont.truetype(FONT_BOLD, size)
    while max(ImageDraw.Draw(Image.new('L', (1, 1))).textbbox((0, 0), l, font=f)[2] for l in text.split('\n')) > W * 0.86 and size > 20:
        size = int(size * 0.92); f = ImageFont.truetype(FONT_BOLD, size)
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    lines = text.split('\n')
    bw = max(d.textbbox((0, 0), l, font=f)[2] for l in lines); lh = round(size * 1.3); bh = lh * len(lines)
    x0 = (W - bw) // 2; y0 = {'top': lb + round(H * 0.06), 'center': (H - bh) // 2, 'lower_third': round(H * 0.62) - lb}.get(pos, lb + round(H * 0.06))
    pad = round(size * 0.45)
    d.rounded_rectangle([x0 - pad, y0 - pad // 2, x0 + bw + pad, y0 + bh + pad // 2], radius=pad // 2, fill=(14, 36, 64, 150))
    for i, l in enumerate(lines):
        lw = d.textbbox((0, 0), l, font=f)[2]
        d.text(((W - lw) // 2, y0 + i * lh), l, font=f, fill=(255, 255, 255, 255))
    a = np.asarray(img).astype(np.float32)
    return a[..., [2, 1, 0]], a[..., 3:4] / 255.0


def slowmo_of(c):
    if c.get('slowmo'): return float(c['slowmo'])
    sp = float(c.get('toc_do', 1.0)); return 1.0 / sp if sp else 1.0


def build_luts(P, C, work):
    """Project 'mau': {"look": "filmic", "khop_mau": true, "tham_chieu": "C02" | "file.mp4@12"} -> {scene_id: [cube files]}."""
    cfg = P.get('mau') or {}
    if not cfg: return {}
    import grade
    out = {}
    look = None
    if cfg.get('look') and cfg['look'] != 'none':
        look = os.path.join(work, f'look_{cfg["look"]}.cube'); grade.write_cube(grade.lut_look(cfg['look'], float(cfg.get('do_manh_look', 1.0))), look)
    ref = None
    if cfg.get('khop_mau'):
        r = cfg.get('tham_chieu')
        sc = next((c for c in C if c['id'] == r), None) if r else next((c for c in C if (c.get('nguon') or {}).get('file')), None)
        if sc is not None:
            n = sc['nguon']; ref = grade.sample_frames(n['anh']) if n.get('anh') else grade.sample_frames(f'{n["file"]}@{float(n.get("vao", 0)) + 1.0}')
        elif r: ref = grade.sample_frames(r)
    for c in C:
        n = c.get('nguon') or {}; lst = []
        if ref is not None and (n.get('file') or n.get('anh')) and not c.get('giu_mau'):
            src = grade.sample_frames(n['anh']) if n.get('anh') else \
                [f for t in (0.5, 1.5, 2.5) for f in grade.sample_frames(f'{n["file"]}@{float(n.get("vao", 0)) + t}')]
            p = os.path.join(work, f'khop_{c["id"]}.cube'); grade.write_cube(grade.lut_match(ref, src, float(cfg.get('do_manh_khop', 0.7))), p)
            lst.append(p)
        if look and (n.get('file') or n.get('anh')): lst.append(look)
        if lst: out[c['id']] = lst
    log(f'màu: {"khớp màu theo " + str(cfg.get("tham_chieu", "cảnh video đầu")) if ref is not None else ""} {("look " + cfg["look"]) if look else ""}')
    return out


STYLES = {
    # phong_cach: defaults applied only where the project/scene does not say otherwise
    'trang_trong': {'chuyen_canh': 'dissolve', 'chuyen_canh_s': 0.7, 'camera': [{'move': 'push_in', 'amount': 0.05}, {'move': 'pull_out', 'amount': 0.05}],
                    'anh': ['zoom_in', 'pan_right', 'zoom_out', 'pan_left'], 'look': 'clean', 'cat_theo_nhac': False},
    'dien_anh': {'chuyen_canh': 'dissolve', 'chuyen_canh_s': 0.9, 'camera': [{'move': 'push_in', 'amount': 0.07}, {'move': 'pan_right', 'amount': 0.06}],
                 'anh': ['zoom_in', 'pan_right', 'pan_left'], 'look': 'filmic', 'letterbox': 2.39, 'cat_theo_nhac': 'downbeat'},
    'tai_lieu': {'chuyen_canh': 'cut', 'chuyen_canh_s': 0.6, 'camera': [{'move': 'push_in', 'amount': 0.04}], 'anh': ['zoom_in', 'pan_right'],
                 'look': 'warm', 'cat_theo_nhac': False},
    'nang_dong': {'chuyen_canh': 'cut', 'chuyen_canh_s': 0.35, 'camera': [{'move': 'push_in', 'amount': 0.10}, {'move': 'pan_left', 'amount': 0.10}],
                  'anh': ['zoom_in', 'zoom_out'], 'look': 'teal_orange', 'cat_theo_nhac': True},
    'mang_xa_hoi': {'chuyen_canh': 'cut', 'chuyen_canh_s': 0.3, 'camera': [{'move': 'push_in', 'amount': 0.12}], 'anh': ['zoom_in'],
                    'look': 'clean', 'cat_theo_nhac': True, 'khung': 'smart'},
}
TRANSITIONS = ('cut', 'dissolve', 'fade_black', 'dip_white', 'wipe_left', 'wipe_right', 'slide_left', 'slide_right', 'zoom_in')


def apply_style(P, C):
    st = STYLES.get(P.get('phong_cach') or '', {})
    if not st: return
    P.setdefault('chuyen_canh_s', st['chuyen_canh_s'])
    if 'cat_theo_nhac' not in P: P['cat_theo_nhac'] = st['cat_theo_nhac']
    if 'mau' not in P: P['mau'] = {'look': st['look'], 'khop_mau': True}
    if st.get('letterbox') and 'letterbox' not in P and P.get('width', 1920) > P.get('height', 1080): P['letterbox'] = st['letterbox']
    if st.get('khung') and 'khung' not in P: P['khung'] = st['khung']
    kv = ka = 0
    for i, c in enumerate(C):
        if 'chuyen_canh' not in c and i + 1 < len(C): c['chuyen_canh'] = st['chuyen_canh']
        n = c.get('nguon') or {}
        if (n.get('file') or n.get('tim')) and 'camera' not in c and not c.get('slowmo'):
            c['camera'] = st['camera'][kv % len(st['camera'])]; kv += 1
        if n.get('anh') and 'hieu_ung' not in n:
            n['hieu_ung'] = st['anh'][ka % len(st['anh'])]; ka += 1
    log(f'phong cách dựng: {P["phong_cach"]}')


def blend(kind, a, b, w):
    """Transition frame: a = outgoing, b = incoming, w = 0..1 (eased)."""
    if kind == 'fade_black': return a * max(0.0, 1 - 2 * w) if w < 0.5 else b * (2 * w - 1)
    if kind == 'dip_white':
        white = np.full_like(a, 255.0)
        return a * (1 - 2 * w) + white * (2 * w) if w < 0.5 else white * (2 - 2 * w) + b * (2 * w - 1)
    h, wd = a.shape[:2]
    if kind in ('wipe_left', 'wipe_right'):
        x = int(round(wd * w)); out = a.copy()
        if kind == 'wipe_left': out[:, wd - x:] = b[:, wd - x:]
        else: out[:, :x] = b[:, :x]
        return out
    if kind in ('slide_left', 'slide_right'):
        x = int(round(wd * w)); out = np.empty_like(a)
        if kind == 'slide_left':
            out[:, :wd - x] = a[:, x:]; out[:, wd - x:] = b[:, :x]
        else:
            out[:, x:] = a[:, :wd - x]; out[:, :x] = b[:, wd - x:]
        return out
    if kind == 'zoom_in':
        import cv2
        z = 1 + 0.25 * w; M = np.float32([[z, 0, wd / 2 * (1 - z)], [0, z, h / 2 * (1 - z)]])
        return cv2.warpAffine(a, M, (wd, h), borderMode=cv2.BORDER_REFLECT) * (1 - w) + b * w
    return a * (1 - w) + b * w                       # dissolve


def resolve_voice(P, c):
    """Scene voice -> character voice -> project voice -> chosen by purpose (voices.suggest). Never a hidden default."""
    v = c.get('giong')
    if not v and c.get('nhan_vat'):
        v = (P.get('nhan_vat', {}).get(c['nhan_vat'][0]) or {}).get('giong')
    v = v or P.get('giong') or P.get('giong_mac_dinh') or 'auto'
    if isinstance(v, dict):
        if v.get('clone'): return 'clone:' + v['clone'], 'nhân bản giọng từ mẫu (cần sự đồng ý của người nói)'
        if v.get('edge'): return 'edge:' + v['edge'], 'Edge TTS'
    if v == 'auto':
        import voices
        md = P.get('muc_dich', 'doanh_nghiep')
        best = voices.suggest(md, P.get('gioi_tinh'), P.get('vung'), 1, P.get('am_sac'))
        return best[0][0], f'tự chọn theo mục đích "{md}": {best[0][2]}'
    return v, 'chỉ định'


def pick_from_library(P, C, NEED_S, root):
    """nguon: {"tim": "english description"} -> best unused shot from the CLIP library (project 'kho_canh')."""
    todo = [i for i, c in enumerate(C) if (c.get('nguon') or {}).get('tim')]
    if not todo: return
    lib_p = P.get('kho_canh'); lib_p = lib_p if (not lib_p or os.path.isabs(lib_p)) else os.path.join(root, lib_p)
    if not lib_p or not os.path.exists(lib_p): raise SystemExit('cảnh có "tim" nhưng thiếu "kho_canh" (chạy shot_select.py scan --clip)')
    import shot_select
    lib = json.load(open(lib_p, encoding='utf8')); used = set()
    for i in todo:
        c = C[i]; q = c['nguon']['tim']; need = NEED_S[i] / slowmo_of(c) + 0.3
        if any(s.get('clip') and 'graphic' not in s for s in lib): lib = shot_select.graphic_scores(lib)
        found = [s for s in shot_select.search(lib, q, top=40) if (s['file'], s['start']) not in used]
        real = [s for s in found if s.get('graphic', 0) < float(P.get('nguong_do_hoa', 0.5))]
        if real: found = real                                   # never pick a slide / foreign graphic when real footage exists
        cands = [s for s in found if s['dur'] >= need] or found
        if not cands: raise SystemExit(f'{c["id"]}: không tìm được cảnh cho "{q}"')
        mx = max(x['match'] for x in cands)
        best = max(cands, key=lambda s: 0.7 * s['match'] / mx + 0.3 * s['score'] / 100)
        if best['match'] < float(P.get('nguong_tim', 0.25)):
            P.setdefault('_canh_can_xem', []).append(c['id'])
            if not P.get('tim_chap_nhan_thap'):        # never show a wrong shot: honest placeholder, flagged in the report
                log(f'  {c["id"]}: KHÔNG có cảnh đủ khớp cho "{q}" (tốt nhất {best["match"]}) -> đặt thẻ giữ chỗ "CẦN CẢNH"')
                c['nguon'] = {'mau': '#1A1F2B'}; c['chu_tren_hinh'] = 'CẦN CẢNH:\n' + q[:48]; c['vi_tri_chu'] = 'center'
                continue
            log(f'  {c["id"]}: CẢNH BÁO - độ khớp thấp ({best["match"]}) cho "{q}": phải xem contact sheet, có thể sai nội dung')
        used.add((best['file'], best['start']))
        c['nguon'] = {'file': best['file'], 'vao': best['start'], 'ra': best['end'], 'bo_qua_kiem_cat': True}
        log(f'  {c["id"]}: "{q}" -> {os.path.basename(best["file"])} {best["start"]:.2f}-{best["end"]:.2f}s (khớp {best["match"]}, điểm {best["score"]})')


def guarded_tts(texts, voice, outdir, threshold, tries, originals=None):
    import accuracy
    os.makedirs(outdir, exist_ok=True)
    key = hashlib.md5(json.dumps([voice, texts, threshold, tries, 2], ensure_ascii=False).encode()).hexdigest()[:10]
    stamp = os.path.join(outdir, f'guard_{key}.json')
    if os.path.exists(stamp):
        d = json.load(open(stamp, encoding='utf8'))
        if all(os.path.exists(f) for f in d['files']): return d['files'], d['rows']
    files, rows = accuracy.guarded_synth(texts, voice, outdir, threshold, tries, log=log, originals=originals)
    json.dump({'files': files, 'rows': rows}, open(stamp, 'w', encoding='utf8'), ensure_ascii=False)
    return files, rows


def make(proj_path, out=None, work=None, no_subs=False, capcut=None):
    P = json.load(open(proj_path, encoding='utf8')); root = os.path.dirname(os.path.abspath(proj_path))
    W, H, fps = int(P.get('width', 1920)), int(P.get('height', 1080)), float(P.get('fps', 25))
    out = out or os.path.join(root, P.get('ten', 'video') + '.mp4'); need_new(out)
    work = os.path.abspath(work or os.path.splitext(out)[0] + '_work'); os.makedirs(work, exist_ok=True)
    rel = lambda p: p if (p is None or os.path.isabs(p)) else os.path.join(root, p)
    C = P['canh']
    for c in C:
        n = c.get('nguon') or {}
        for k in ('file', 'anh', 'html'):
            if n.get(k): n[k] = rel(n[k])
            if n.get(k) and not os.path.exists(n[k]): raise SystemExit(f'{c["id"]}: không thấy {n[k]}')
    apply_style(P, C)
    for c in C:
        if P.get('khung') and 'khung' not in c: c['khung'] = P['khung']
    warn = P.setdefault('_canh_bao', [])
    for c in C:
        sn = set(re.findall(r'\d[\d.,]*', c.get('chu_tren_hinh') or '')) - set(re.findall(r'\d[\d.,]*', c.get('thoai') or ''))
        if sn and c.get('thoai'): warn.append(f"{c['id']}: số trên hình {sorted(sn)} không có trong lời đọc - kiểm tra đồng bộ")
    # anti AI-slop (deterministic): script clichés, unsourced numbers/claims, uniform editing, client rule ledger
    import slop_guard
    sfacts, srules, smiss = slop_guard.project_sources(P, root)
    slop = slop_guard.run_project(P, sfacts, srules)
    slop['_thieu'] = smiss
    json.dump(slop, open(os.path.join(work, 'slop.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    if P.get('chan_khi_slop') and slop['ket_luan'] == 'CHẶN':
        raise SystemExit(slop_guard.to_md(slop, P.get('ten', '')) + '\n\nDừng vì chan_khi_slop=true. Sửa theo /video:slop rồi dựng lại.')
    td = float(P.get('chuyen_canh_s', 0.5)); T = int(round(td * fps))
    # 1. voices: per scene / character / project / by purpose; pronunciation dictionary; listen-back + re-takes
    import accuracy
    pdict = accuracy.load_dict(P.get('phat_am'))
    vfiles, by_voice, vrows, vnote = [None] * len(C), {}, {}, {}
    for i, c in enumerate(C):
        if c.get('ghi_am'):                                # own recorded narration for this scene
            vfiles[i] = rel(c['ghi_am']); continue
        if c.get('thoai'):
            v, why = resolve_voice(P, c); by_voice.setdefault(v, []).append(i); vnote[v] = why
    if len(by_voice) > 1 and not P.get('nhan_vat'):
        warn.append(f'Phim dùng {len(by_voice)} giọng ({", ".join(by_voice)}) mà không khai báo nhân vật: người xem sẽ thấy đổi giọng vô cớ')
    for w_ in warn: log('  CẢNH BÁO: ' + w_)
    for v, idx in by_voice.items():
        log(f'Giọng {v} ({vnote[v]}): {len(idx)} câu')
        spoken = [accuracy.apply_dict(C[i]['thoai'], pdict) for i in idx]
        fs, rows = guarded_tts(spoken, v, os.path.join(work, 'tts'), float(P.get('do_chinh_xac', 0.97)), int(P.get('doc_lai', 3)),
                               [C[i]['thoai'] for i in idx])
        for i, f, r in zip(idx, fs, rows):
            vfiles[i] = f; vrows[i] = dict(r, giong=v)
    lead = float(P.get('lead_s', 0.35)); tail = float(P.get('tail_s', 0.55))
    # 2. durations
    N, NEED = [], []
    pick_from_library(P, C, [max(float(c.get('thoi_luong') or 0), (wav_dur(vfiles[i]) + lead + tail) if vfiles[i] else 0, 1.5)
                             for i, c in enumerate(C)], root)
    for i, c in enumerate(C):
        need = (wav_dur(vfiles[i]) / float(P.get('slow', 1.0)) + lead + tail) if vfiles[i] else 0.0
        d = max(float(c.get('thoi_luong') or 0), need, 1.5)
        n = c.get('nguon') or {}
        if n.get('file') and not n.get('bo_qua_kiem_cat'):
            sp = 1.0 / slowmo_of(c)              # source seconds per output second
            extra = td if (c.get('chuyen_canh', 'cut') != 'cut' and i + 1 < len(C)) else 0.0
            a0, a1, note = safe_range(n, (d + extra) * sp)
            if note:
                log(f'  {c["id"]}: {note}')
                c['nguon'] = dict(n, vao=a0, ra=a1, bo_qua_kiem_cat=True)
                avail = (a1 - a0) / sp - extra
                if avail < d:
                    if avail >= max(need, 1.0):
                        log(f'  {c["id"]}: rút cảnh còn {avail:.2f}s để không phải giữ khung đứng hình'); d = avail
                    else:
                        log(f'  {c["id"]}: CẢNH BÁO - nguồn sạch chỉ {avail:.2f}s, cần {d:.2f}s: chọn đoạn nguồn khác')
        N.append(int(round(d * fps))); NEED.append(max(need, 1.5))
    mus = (P.get('nhac') or {}).get('file'); mus = rel(mus) if mus else None
    if P.get('cat_theo_nhac') and mus:            # cut on the music: move each boundary to the nearest beat if allowed
        import deliver
        tempo, beats_t, downs = deliver.beats(mus)
        grid = downs if P.get('cat_theo_nhac') == 'downbeat' else beats_t
        t = 0.0; moved = 0
        for i in range(len(N) - 1):
            end = (t * fps + N[i]) / fps; tgt = deliver.snap(end, grid, 0.45)
            if tgt != end and (tgt - t) >= NEED[i]:
                N[i] = int(round((tgt - t) * fps)); moved += 1
            t += N[i] / fps
        log(f'cắt theo nhạc: {tempo:.0f} BPM, {moved}/{len(N) - 1} điểm cắt đã khớp phách')
    starts = np.r_[0, np.cumsum(N)[:-1]].astype(int); total = int(sum(N))
    luts = build_luts(P, C, work)
    log(f'{len(C)} cảnh, {total} khung = {total / fps:.2f} s @ {fps} fps')
    # 3. pictures
    silent = os.path.join(work, 'hinh.mp4')
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(fps),
                            '-i', '-', '-c:v', 'libx264', '-crf', '16', '-preset', 'medium', '-pix_fmt', 'yuv420p',
                            '-g', str(int(fps * 2)), '-movflags', '+faststart', silent], stdin=subprocess.PIPE)
    pend, written, pend_kind = None, 0, 'dissolve'
    planned = []
    lb = int(round((H - W / float(P['letterbox'])) / 2)) if P.get('letterbox') and W / H < float(P['letterbox']) else 0
    fade_in = int(round(fps * 0.5)) if P.get('mo_dau_fade', True) else 0
    fade_out = int(round(fps * 0.8)) if P.get('ket_fade', True) else 0
    for i, c in enumerate(C):
        n = c.get('nguon') or {}
        kind = c.get('chuyen_canh', 'cut'); diss = kind != 'cut' and i + 1 < len(C)
        if diss: planned.append(((starts[i + 1] - 1) / fps, (starts[i + 1] + T + 1) / fps, kind))
        if n.get('mau') and sum(hex_bgr(n['mau'])) < 90: planned.append((starts[i] / fps, (starts[i] + N[i]) / fps, 'thẻ nền tối'))
        L = N[i] + (T if diss else 0)
        lut_vf = ','.join(f"lut3d=file='{os.path.basename(x)}':interp=tetrahedral" for x in luts.get(c['id'], []))
        if n.get('html'):
            import motion_html
            key = hashlib.md5(json.dumps([n['html'], os.path.getmtime(n['html']), n.get('params'), L, fps, W, H], ensure_ascii=False).encode()).hexdigest()[:10]
            mp = os.path.join(work, 'clips', f'html_{key}.mp4'); os.makedirs(os.path.dirname(mp), exist_ok=True)
            if not os.path.exists(mp):
                log(f'  {c["id"]}: dựng đồ hoạ động {os.path.basename(n["html"])}')
                motion_html.render(n['html'], mp, L / fps, fps, W, H, n.get('sub', 'auto'), n.get('params'))
            gen = video_frames({'file': mp, 'vao': 0}, W, H, fps, L, 1.0, lut_vf if n.get('ap_mau') else '', cwd=work)
        elif n.get('file'):
            if not n.get('bo_qua_kiem_cat'):
                a0, a1, note = safe_range(n, L / fps / slowmo_of(c))
                if note:
                    log(f'  {c["id"]}: {note}'); n = dict(n, vao=a0, ra=a1)
            clip = prepare_clip(c, n, W, H, fps, L, work)
            gen = video_frames({'file': clip, 'vao': 0}, W, H, fps, L, 1.0, ','.join(x for x in [n.get('vf', ''), lut_vf] if x), cwd=work)
        elif n.get('anh'):
            if lut_vf:
                g = os.path.join(work, f'anh_{c["id"]}.png')
                subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', n['anh'], '-vf', lut_vf, os.path.basename(g)], cwd=work, check=True)
                n = dict(n, anh=g)
            gen = image_frames(n, W, H, L)
        else:
            gen = color_card(hex_bgr(n.get('mau', '#000000')), W, H, L)
        lay = text_layer(c['chu_tren_hinh'], W, H, c.get('vi_tri_chu', 'top'), lb) if c.get('chu_tren_hinh') else None
        buf = []
        cam = c.get('camera')
        t_in = 0.3                                   # when the on-screen text appears (s from scene start)
        if lay is not None and vfiles[i] and c.get('thoai'):
            m = re.search(r'\d', c['chu_tren_hinh']); num = re.search(r'\d[\d.,]*', c['chu_tren_hinh'])
            pos = c['thoai'].find(num.group(0).rstrip('.,')) if num else -1
            if pos > 0: t_in = lead + wav_dur(vfiles[i]) * pos / max(1, len(c['thoai'])) - 0.15
        for k, fr in enumerate(gen):
            if cam and n.get('file'): fr = cam_warp(fr, k, L, cam)
            fr = fr.astype(np.float32)
            if lb:
                fr[:lb] = 0; fr[H - lb:] = 0
            if lay is not None:
                a_in = min(1.0, max(0.0, (k - fps * t_in) / (fps * 0.45))); a_out = min(1.0, max(0.0, (N[i] - k - fps * 0.2) / (fps * 0.5)))
                a = min(a_in, a_out)
                if a > 0: fr = fr * (1 - lay[1] * a) + lay[0] * lay[1] * a
            if pend is not None and k < len(pend):
                w = (k + 1) / (len(pend) + 1); w = w * w * (3 - 2 * w)
                fr = blend(pend_kind, pend[k], fr, w)
            if diss and k >= N[i]: buf.append(fr); continue
            g = starts[i] + k
            if g < fade_in: fr = fr * (g / fade_in)
            if g >= total - fade_out: fr = fr * max(0.0, (total - 1 - g) / fade_out)
            enc.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes()); written += 1
        pend = buf if diss else None; pend_kind = kind
        log(f'  cảnh {c["id"]}: {N[i] / fps:.2f}s {("+ " + kind) if diss else ""}')
    enc.stdin.close(); enc.wait()
    # 4. sound
    lines = [((starts[i] / fps), (starts[i] + N[i]) / fps, C[i].get('thoai', '')) for i in range(len(C))]
    mixed = os.path.join(work, 'co_tieng.mp4')
    if os.path.exists(mixed): os.replace(mixed, mixed + '.old')
    used = voice_mix.mix_voice(lines, vfiles, silent, mixed, mus, float(P.get('lufs', -16)), lead=lead,
                               slow=float(P.get('slow', 1.0)), music_gain=float((P.get('nhac') or {}).get('gain', 1.0)),
                               total=total / fps)
    # 5. subtitles
    srt = None
    spoken = [(u[0], u[1], C[i]['thoai']) for i, u in enumerate(used) if u]
    if spoken:
        import accuracy as _acc
        stem0 = os.path.splitext(mixed)[0] + '_voice.wav'
        cues = subs.make_cues_aligned(spoken, stem0, fps, _acc.model()); srt = os.path.splitext(out)[0] + '.srt'
        subs.write_srt(cues, srt); ass = os.path.join(work, 'phu_de.ass'); subs.write_ass(cues, ass, W, H)
    if srt and P.get('phu_de', True) and not no_subs:
        log('burn phụ đề'); subs.burn(mixed, ass, out)
    else:
        shutil.copy(mixed, out)
    extra = []
    stem = os.path.splitext(mixed)[0] + '_voice.wav'
    if spoken:
        acc, errs, _ = speech_accuracy(stem, [t for *_, t in spoken])
        acc2, errs2, _ = speech_accuracy(stem, [accuracy.apply_dict(t, pdict) for *_, t in spoken])
        if acc2 > acc: acc, errs = acc2, errs2
        extra = [f'- Lời đọc khớp kịch bản (toàn phim): {acc * 100:.1f} %'] + [f'  - "{a}" -> nghe "{b}"' for a, b in errs[:15]]
        extra += ['', '## Từng câu (sau khi tự đọc lại câu sai)', '| Cảnh | Giọng | Khớp | Nghe được |', '|---|---|---|---|']
        thr = float(P.get('do_chinh_xac', 0.97))
        for i, r in sorted(vrows.items()):
            extra.append(f"| {C[i]['id']} | {r['giong']} | {r['acc'] * 100:.0f}%{' (thấp)' if r['acc'] < thr else ''} | {r['nghe']} |")
        extra += ['', '## Giọng đã chọn'] + [f'- {v}: {w}' for v, w in vnote.items()]
    if P.get('_canh_bao'):
        extra += ['', '## Cảnh báo dựng'] + [f'- {w}' for w in P['_canh_bao']]
    sm = slop_guard.to_md(slop, P.get('ten', '')).split('\n', 2)[2]
    extra += ['', '## Chống AI slop (hệ 0 - tất định; xử lý bằng /video:slop)'] + [l.replace('## ', '### ') for l in sm.split('\n')]
    if not sfacts: extra.append('- Chưa có `facts` trong project: số liệu chưa được đối chiếu nguồn')
    if smiss: extra.append(f'- Không thấy file: {smiss}')
    if P.get('_canh_can_xem'):
        extra += ['', f"## Cảnh tự chọn cần xem bằng mắt (độ khớp thấp): {', '.join(P['_canh_can_xem'])}"]
    if mus and P.get('ban_chi_nhac', True):                 # deliverable: picture + music only (no voice)
        mo = os.path.splitext(out)[0] + '_chi_nhac.mp4'
        if not os.path.exists(mo):
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', silent, '-stream_loop', '-1', '-i', mus, '-map', '0:v', '-map', '1:a',
                            '-c:v', 'copy', '-af', f'afade=t=out:st={max(0, total / fps - 2):.2f}:d=2,loudnorm=I={float(P.get("lufs", -16))}:TP=-1.5',
                            '-c:a', 'aac', '-b:a', '256k', '-t', f'{total / fps:.3f}', mo], check=True)
            extra.append(f'- Bản chỉ có nhạc: {os.path.basename(mo)}')
    json.dump([list(x) for x in planned], open(os.path.splitext(out)[0] + '_plan.json', 'w', encoding='utf8'), ensure_ascii=False)
    report(out, work, extra=extra, ignore=planned)
    if capcut: to_capcut(capcut, silent, stem, mus, srt, W, H)
    log('XONG ->', out)


# ---------------------------------------------------------------- revoice
def separate(video, work):
    d = os.path.join(work, 'tach')
    if not (os.path.exists(os.path.join(d, 'voice.wav')) and os.path.exists(os.path.join(d, 'music.wav'))):
        log('Demucs tách giọng/nhạc')
        subprocess.run([sys.executable, os.path.join(HERE, 'demucs_split.py'), video, d], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return os.path.join(d, 'voice.wav'), os.path.join(d, 'music.wav')


def revoice(video, script, voice, out, work=None, no_subs=True, lufs=-16, slow=1.0, capcut=None, keep_music=True,
            muc_dich='doanh_nghiep', gioi_tinh=None, vung=None, phat_am=None, threshold=0.97):
    need_new(out)
    work = work or os.path.splitext(out)[0] + '_work'; os.makedirs(work, exist_ok=True)
    info = probe(video); T = info['duration']
    S = read_script(script); texts = [t for *_, t in S]
    old_voice, music = separate(video, work)
    if S[0][0] is None:
        log('Dò mốc từng câu trên giọng cũ (Whisper)')
        times = align(old_voice, texts)
        for (s, e), t in zip(times, texts): log(f'  {s:6.2f}-{e:6.2f}  {t[:60]}')
        slots = slots_from_times(times, T)
    else:
        slots = [(s, e) for s, e, _ in S]
    json.dump([[s, e, t] for (s, e), t in zip(slots, texts)], open(os.path.join(work, 'script_moc.json'), 'w', encoding='utf8'),
              ensure_ascii=False, indent=1)
    v, why = resolve_voice({'giong': voice, 'muc_dich': muc_dich, 'gioi_tinh': gioi_tinh, 'vung': vung}, {})
    log(f'Giọng {v} ({why})')
    import accuracy
    pd = accuracy.load_dict(json.load(open(phat_am, encoding='utf8')) if phat_am else None)
    files, rows = guarded_tts([accuracy.apply_dict(t, pd) for t in texts], v, os.path.join(work, 'tts'), threshold, 3, texts)
    voice = v
    mixed = os.path.join(work, 'co_tieng.mp4')
    if os.path.exists(mixed): os.replace(mixed, mixed + '.old')
    used = voice_mix.mix_voice([(s, e, t) for (s, e), t in zip(slots, texts)], files, video, mixed,
                               music if keep_music else None, lufs, lead=0.0, slow=slow, total=T)
    import accuracy as _acc
    cues = subs.make_cues_aligned([(u[0], u[1], t) for u, t in zip(used, texts) if u], os.path.splitext(mixed)[0] + '_voice.wav',
                                  info['fps'] or 25, _acc.model())
    srt = os.path.splitext(out)[0] + '.srt'; subs.write_srt(cues, srt)
    if not no_subs:
        ass = os.path.join(work, 'phu_de.ass'); subs.write_ass(cues, ass, info['width'], info['height']); subs.burn(mixed, ass, out)
    else:
        shutil.copy(mixed, out)
    stem = os.path.splitext(mixed)[0] + '_voice.wav'
    acc, errs, _ = speech_accuracy(stem, texts)
    report(out, work, extra=[f'- Giọng: {voice} ({why})', f'- Lời đọc khớp kịch bản: {acc * 100:.1f} %'] +
           [f'  - "{a}" -> nghe "{b}"' for a, b in errs[:15]] +
           ['', '| Câu | Khớp | Nghe được |', '|---|---|---|'] + [f"| {r['cau']} | {r['acc'] * 100:.0f}% | {r['nghe']} |" for r in rows])
    if capcut:
        sil = os.path.join(work, 'hinh_khong_tieng.mp4')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', video, '-an', '-c:v', 'copy', sil], check=True)
        to_capcut(capcut, sil, stem, music if keep_music else None, srt, info['width'], info['height'])
    log(f'XONG -> {out}  (lời khớp {acc * 100:.1f} %)')


def subs_cmd(video, script, out, work=None, from_audio=False):
    need_new(out)
    work = work or os.path.splitext(out)[0] + '_work'; os.makedirs(work, exist_ok=True)
    info = probe(video); S = read_script(script); texts = [t for *_, t in S]
    if S[0][0] is None or from_audio:
        voice, _ = separate(video, work); times = align(voice, texts)
    else:
        times = [(s, e) for s, e, _ in S]
    if S[0][0] is None or from_audio:
        import accuracy as _acc
        cues = subs.make_cues_aligned([(s, e, t) for (s, e), t in zip(times, texts)], voice, info['fps'] or 25, _acc.model())
    else:
        cues = subs.make_cues([(s, e, t) for (s, e), t in zip(times, texts)], info['fps'] or 25)
    srt = os.path.splitext(out)[0] + '.srt'; subs.write_srt(cues, srt)
    ass = os.path.join(work, 'phu_de.ass'); subs.write_ass(cues, ass, info['width'], info['height'])
    subs.burn(video, ass, out); log('XONG ->', out, '+', srt)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    m = sp.add_parser('make'); m.add_argument('project'); m.add_argument('--out'); m.add_argument('--work')
    m.add_argument('--no-subs', action='store_true'); m.add_argument('--capcut')
    r = sp.add_parser('revoice'); r.add_argument('video'); r.add_argument('--script', required=True)
    r.add_argument('--voice', default='auto', help='tên giọng | edge:<ShortName> | clone:<mau.wav> | auto (chọn theo --muc-dich)');
    r.add_argument('--muc-dich', default='doanh_nghiep'); r.add_argument('--gioi-tinh', choices=['nam', 'nu']); r.add_argument('--vung', choices=['bac', 'trung', 'nam'])
    r.add_argument('--phat-am', help='JSON từ điển phát âm riêng'); r.add_argument('--do-chinh-xac', type=float, default=0.97); r.add_argument('--out', required=True); r.add_argument('--work')
    r.add_argument('--subs', action='store_true', help='burn phụ đề vào hình'); r.add_argument('--lufs', type=float, default=-16)
    r.add_argument('--slow', type=float, default=1.0); r.add_argument('--capcut'); r.add_argument('--no-music', action='store_true')
    s = sp.add_parser('subs'); s.add_argument('video'); s.add_argument('--script', required=True); s.add_argument('--out', required=True)
    s.add_argument('--work'); s.add_argument('--from-audio', action='store_true')
    q = sp.add_parser('qc'); q.add_argument('video'); q.add_argument('--ref')
    a = ap.parse_args()
    if a.cmd == 'make': make(a.project, a.out, a.work, a.no_subs, a.capcut)
    elif a.cmd == 'revoice': revoice(a.video, a.script, a.voice, a.out, a.work, not a.subs, a.lufs, a.slow, a.capcut, not a.no_music,
                                     a.muc_dich, a.gioi_tinh, a.vung, a.phat_am, a.do_chinh_xac)
    elif a.cmd == 'subs': subs_cmd(a.video, a.script, a.out, a.work, a.from_audio)
    else:
        w = os.path.splitext(a.video)[0] + '_qc'; os.makedirs(w, exist_ok=True); report(a.video, w)


if __name__ == '__main__':
    main()
