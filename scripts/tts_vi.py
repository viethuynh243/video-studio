"""Vietnamese TTS with VieNeu-TTS (open source, Apache 2.0, CPU/ONNX, 25 preset voices incl. Northern male).

  python tts_vi.py --list                                      # list preset voices (gender, region, style)
  python tts_vi.py script.json OUTDIR --voices "Thiện Minh" "Minh Đức"     # one wav per line per voice
  python tts_vi.py --text "Câu thử." OUTDIR --voices "Thiện Minh"

script.json: [[start, end, "text"], ...]  or  [{"start":..,"end":..,"text":..}, ...]  or  ["text", ...]
Output: OUTDIR/<VoiceAscii>_<i>.wav (48 kHz) and OUTDIR/<VoiceAscii>_all.wav (lines joined, 0.35 s gaps).
Text is normalised for Vietnamese TTS (hyphens/dashes read as "đến", units) unless --no-normalize.

Runs inside the VieNeu venv automatically (env VIENEU_PY, default ~/tools/venv_vieneu).
Install once:  python -m venv ~/tools/venv_vieneu && ~/tools/venv_vieneu/Scripts/pip install vieneu   (install.ps1 does it)
"""
import argparse, json, os, re, subprocess, sys, unicodedata

VENV_PY = os.environ.get('VIENEU_PY', os.path.expanduser('~/tools/venv_vieneu/Scripts/python.exe'))


def ensure_venv():
    try:
        import vieneu  # noqa: F401
    except ImportError:
        if os.path.exists(VENV_PY) and os.path.abspath(sys.executable).lower() != os.path.abspath(VENV_PY).lower():
            env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
            sys.exit(subprocess.call([VENV_PY, __file__] + sys.argv[1:], env=env))
        sys.exit('vieneu not installed - see --help for the one-time install')


UNITS = [(r'(\d)\s*km/h\b', r'\1 ki lô mét trên giờ'), (r'\bkm/h\b', 'ki lô mét trên giờ'),
         (r'(\d)\s*km\b', r'\1 ki lô mét'), (r'(\d)\s*m2\b', r'\1 mét vuông'), (r'(\d)\s*ha\b', r'\1 héc ta'),
         (r'(\d)\s*%', r'\1 phần trăm')]


def normalize(t):
    t = t.replace('ki-lô-mét', 'ki lô mét').replace('Ki-lô-mét', 'Ki lô mét')
    t = re.sub(r'(\d{4})\s*[-–—]\s*(\d{4})', r'\1 đến \2', t)          # year ranges: say "đến" explicitly
    t = re.sub(r'\s*[–—]\s*', ', ', t)                                  # dashes between names -> pause, not "đến"
    t = re.sub(r'(?<=\w)-(?=\w)', ' ', t)                               # hyphenated syllables
    for p, r in UNITS: t = re.sub(p, r, t)
    t = re.sub(r'\s+,', ',', re.sub(r'\s{2,}', ' ', t)).strip()
    return t


def ascii_name(v):
    v = v.replace('đ', 'd').replace('Đ', 'D')
    return ''.join(c for c in unicodedata.normalize('NFD', v) if unicodedata.category(c) != 'Mn' and c.isalnum())


def load_lines(path):
    d = json.load(open(path, encoding='utf8'))
    out = []
    for x in d:
        if isinstance(x, str): out.append(x)
        elif isinstance(x, dict): out.append(x['text'])
        else: out.append(x[2])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('script', nargs='?'); ap.add_argument('outdir', nargs='?')
    ap.add_argument('--text'); ap.add_argument('--voices', nargs='+', default=['Thiện Minh'])
    ap.add_argument('--list', action='store_true'); ap.add_argument('--no-normalize', action='store_true')
    a = ap.parse_args()
    if a.text and a.script and not a.outdir: a.outdir, a.script = a.script, None
    ensure_venv()
    from vieneu import Vieneu
    tts = Vieneu()
    if a.list:
        for label, v in tts.list_preset_voices(): print(label.replace('⭐', '*'))
        return
    lines = [a.text] if a.text else load_lines(a.script)
    if not a.no_normalize: lines = [normalize(t) for t in lines]
    os.makedirs(a.outdir, exist_ok=True)
    for v in a.voices:
        tag = ascii_name(v); files = []
        for i, t in enumerate(lines):
            p = os.path.join(a.outdir, f'{tag}_{i}.wav'); tts.save(tts.infer(t, voice=v), p); files.append(p)
            print(f'{v} {i}: {t}')
        if len(files) > 1:
            gap = os.path.join(a.outdir, '_gap.wav')
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=mono', '-t', '0.35', gap])
            seq = sum([[f, gap] for f in files], [])[:-1]
            subprocess.run(['ffmpeg', '-v', 'error', '-y'] + sum([['-i', f] for f in seq], []) + ['-filter_complex',
                           ''.join(f'[{k}]aresample=48000,aformat=channel_layouts=mono[a{k}];' for k in range(len(seq))) +
                           ''.join(f'[a{k}]' for k in range(len(seq))) + f'concat=n={len(seq)}:v=0:a=1',
                           os.path.join(a.outdir, f'{tag}_all.wav')])
            os.remove(gap)


if __name__ == '__main__':
    main()
