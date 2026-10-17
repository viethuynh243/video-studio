"""Subtitles: split narration into readable cues, write SRT/ASS, burn into a video.

  python subs.py cues  script.json out.srt [--ass out.ass]     # script lines [[start,end,text],...] -> cues
  python subs.py burn  VIDEO.mp4 subs.ass OUT.mp4               # burn ASS (libass), audio copied

Rules (see references/06): <= 2 lines, <= 42 chars per line, <= 17 chars/s when possible, split at punctuation,
no em dash, 2-frame gap between cues. Importable: make_cues(lines), write_srt(cues, p), write_ass(cues, p, W, H), burn(...).
"""
import argparse, json, os, re, shutil, subprocess, tempfile

MAXL, MAXC = 42, 76


def clean(t):
    t = re.sub(r'\s*—\s*', ', ', t)
    return re.sub(r'\s+', ' ', t).strip()


def chunks(text):
    """Split a sentence into pieces of <= MAXC chars, preferring punctuation, then word boundaries."""
    text = clean(text)
    if len(text) <= MAXC: return [text]
    parts, cur = [], ''
    for seg in re.split(r'(?<=[,;:.!?])\s+', text):
        if len(cur) + len(seg) + 1 <= MAXC: cur = (cur + ' ' + seg).strip()
        else:
            if cur: parts.append(cur)
            while len(seg) > MAXC:
                cut = seg.rfind(' ', 0, MAXC); cut = cut if cut > 20 else MAXC
                parts.append(seg[:cut].strip()); seg = seg[cut:].strip()
            cur = seg
    if cur: parts.append(cur)
    return parts


def two_lines(t):
    """Break into 2 lines: minimise the longer line, prefer a break after punctuation, never split a number from its unit."""
    if len(t) <= MAXL: return t
    cands = [m.start() for m in re.finditer(' ', t)]
    def score(i):
        a, b = t[:i].strip(), t[i:].strip()
        sc = max(len(a), len(b)) + (40 if max(len(a), len(b)) > MAXL else 0)
        if t[i - 1] in ',;:.': sc -= 10
        if t[i - 1].isdigit(): sc += 8
        return sc
    best = min(cands, key=score)
    return t[:best].strip() + '\n' + t[best:].strip()


def make_cues(lines, fps=25):
    """lines: [(start, end, text)] where (start, end) is when the voice actually speaks. Returns [(s, e, text)]."""
    cues, gap = [], 2.0 / fps
    for s, e, t in lines:
        ps = chunks(t); tot = sum(len(p) for p in ps); cur = s
        for p in ps:
            d = (e - s) * len(p) / tot
            cues.append([cur, cur + d, two_lines(p)]); cur += d
    for a, b in zip(cues, cues[1:]):
        if b[0] - a[1] < gap: a[1] = b[0] - gap
    return [(round(a, 3), round(b, 3), t) for a, b, t in cues]


def make_cues_aligned(lines, stem, fps=25, model=None):
    """Like make_cues but cue boundaries come from Whisper word timestamps on the placed voice stem,
    so every subtitle starts/ends with the words actually spoken. Falls back to make_cues per line."""
    if model is None:
        from faster_whisper import WhisperModel
        model = WhisperModel('medium', device='cpu', compute_type='int8')
    segs, _ = model.transcribe(stem, language='vi', word_timestamps=True, vad_filter=True)
    words = [w for s in segs for w in s.words]
    cues, gap = [], 2.0 / fps
    for s, e, t in lines:
        ws = [w for w in words if w.start >= s - 0.25 and w.end <= e + 0.4]
        ps = chunks(t)
        if len(ws) < 2 or len(ps) == 1:
            st = ws[0].start if ws else s; en = ws[-1].end if ws else e
            cues.append([st, en + 0.15, two_lines(ps[0])] if len(ps) == 1 else None)
            if len(ps) > 1: cues.pop(); cues += [list(c) for c in make_cues([(st, en, t)], fps)]
            continue
        n_ref = [len(re.findall(r'\w+', p)) for p in ps]; tot = sum(n_ref); k0 = 0
        for j, p in enumerate(ps):
            k1 = len(ws) if j == len(ps) - 1 else min(len(ws) - 1, max(k0 + 1, round(len(ws) * sum(n_ref[:j + 1]) / tot)))
            cues.append([ws[k0].start, ws[k1 - 1].end + 0.15, two_lines(p)]); k0 = k1
    cues = [c for c in cues if c]
    for a, b in zip(cues, cues[1:]):
        if b[0] - a[1] < gap: a[1] = b[0] - gap
    return [(round(a, 3), round(b, 3), t) for a, b, t in cues]


def ts(x, srt=True):
    h, m = int(x // 3600), int(x % 3600 // 60); s = x % 60
    return f'{h:02d}:{m:02d}:{s:06.3f}'.replace('.', ',') if srt else f'{h:d}:{m:02d}:{s:05.2f}'


def write_srt(cues, p):
    with open(p, 'w', encoding='utf8') as f:
        for i, (s, e, t) in enumerate(cues, 1): f.write(f'{i}\n{ts(s)} --> {ts(e)}\n{t}\n\n')


def write_ass(cues, p, W=1920, H=1080, font='Arial', size=None, margin_v=None):
    size = size or round(min(W, H) * 0.056 if H > W else H * 0.056); margin_v = margin_v or round(H * 0.06)
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{font},{size},&H00FFFFFF,&H000000FF,&H00000000,&H78000000,-1,0,0,0,100,100,0,0,1,{max(3, round(size / 14))},2,2,80,80,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    with open(p, 'w', encoding='utf8') as f:
        f.write(head)
        for s, e, t in cues: f.write(f'Dialogue: 0,{ts(s, False)},{ts(e, False)},Sub,,0,0,0,,{t.replace(chr(10), chr(92) + "N")}\n')


def burn(video, ass, out, crf=16):
    """Burn ASS with libass. Runs from a temp dir so Windows paths need no escaping."""
    d = tempfile.mkdtemp(); shutil.copy(ass, os.path.join(d, 's.ass'))
    r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.abspath(video), '-vf', 'ass=s.ass',
                        '-c:v', 'libx264', '-crf', str(crf), '-preset', 'slow', '-pix_fmt', 'yuv420p', '-c:a', 'copy',
                        '-movflags', '+faststart', os.path.abspath(out)], cwd=d, capture_output=True, text=True)
    if r.returncode: raise RuntimeError(r.stderr[-800:])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['cues', 'burn']); ap.add_argument('a'); ap.add_argument('b'); ap.add_argument('c', nargs='?')
    ap.add_argument('--ass'); ap.add_argument('--fps', type=float, default=25)
    a = ap.parse_args()
    if a.cmd == 'cues':
        S = json.load(open(a.a, encoding='utf8'))
        S = [(x['start'], x['end'], x['text']) if isinstance(x, dict) else tuple(x) for x in S]
        cues = make_cues(S, a.fps); write_srt(cues, a.b)
        if a.ass: write_ass(cues, a.ass)
        print(len(cues), 'cues ->', a.b)
    else:
        if os.path.exists(a.c): raise SystemExit(f'{a.c} exists')
        burn(a.a, a.b, a.c); print('burned ->', a.c)


if __name__ == '__main__':
    main()
