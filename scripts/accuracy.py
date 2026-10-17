"""Accuracy guard for narration: pronunciation dictionary + per-line listen-back + automatic re-takes.

  python accuracy.py check  LINES.json WAV_DIR TAG              # score each <TAG>_<i>.wav against its text
  python accuracy.py dict   "ABC là đơn vị tư vấn"              # show how the dictionary rewrites a line

Pipeline used by autovideo.py:
  1. apply_dict(): rewrite words the TTS cannot say (acronyms, brand names, foreign words) with a spoken form.
     Global dictionary: templates/phat_am.json; per project: "phat_am": {"BIM": "bim", ...}. Subtitles keep the original.
  2. synthesise every line, then Whisper listens to each line and compares it with the spoken text.
  3. lines under the threshold are re-generated (lower temperature each try, up to N tries); the best take wins.
  4. a report lists every line still under the threshold, with what was heard, so a human can fix the wording.
"""
import argparse, difflib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DICT_FILE = os.path.join(os.path.dirname(HERE), 'templates', 'phat_am.json')
_model = None


def load_dict(extra=None):
    d = json.load(open(DICT_FILE, encoding='utf8')) if os.path.exists(DICT_FILE) else {}
    d = {k: v for k, v in d.items() if not k.startswith('_')}
    d.update(extra or {})
    return d


def apply_dict(text, d):
    for k in sorted(d, key=len, reverse=True):               # longest first
        text = re.sub(r'(?<!\w)' + re.escape(k) + r'(?!\w)', d[k], text)
    return text


def model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel('medium', device='cpu', compute_type='int8')
    return _model


def score(wav, text):
    sys.path.insert(0, HERE); import speech_check as sc
    segs, _ = model().transcribe(wav, language='vi', beam_size=5, initial_prompt=None)
    heard = ' '.join(s.text.strip() for s in segs)
    ref = sc.spelled_to_digits(sc.tok(text)); hyp = sc.spelled_to_digits(sc.tok(heard))
    sm = difflib.SequenceMatcher(None, ref, hyp, autojunk=False)
    acc = sum(n for *_, n in sm.get_matching_blocks()) / max(1, len(ref))
    errs = [(' '.join(ref[a1:a2]), ' '.join(hyp[b1:b2])) for op, a1, a2, b1, b2 in sm.get_opcodes() if op != 'equal']
    return acc, heard, errs


def score_best(wav, spoken, original=None):
    """Score against the spoken form AND the original wording (ASR often writes acronyms/numbers the original way)."""
    a = score(wav, spoken)
    if original and original != spoken:
        b = score(wav, original)
        return b if b[0] > a[0] else a
    return a


def guarded_synth(texts, voice, outdir, threshold=0.97, tries=3, log=print, originals=None):
    """Synthesise + listen + re-take. Returns (files, report rows). Uses voices.synth for any engine."""
    sys.path.insert(0, HERE); import voices, shutil
    files = voices.synth(texts, voice, outdir)
    orig = originals or [None] * len(texts)
    best = {i: (score_best(f, t, orig[i]), f) for i, (f, t) in enumerate(zip(files, texts))}
    temps = [0.65, 0.5, 0.4]
    for k in range(tries - 1 if not voice.startswith('edge:') else 0):
        bad = [i for i, ((acc, _, _), _) in best.items() if acc < threshold]
        if not bad: break
        log(f'  đọc lại {len(bad)} câu (lần {k + 2}, temperature {temps[k]}): {[i + 1 for i in bad]}')
        alt = voices.synth(texts, voice, outdir, temperature=temps[k], suffix=f'_r{k + 2}', only=bad)
        for i in bad:
            r = score_best(alt[i], texts[i], orig[i])
            if r[0] > best[i][0][0]: best[i] = (r, alt[i])
    out, rows = [], []
    for i, t in enumerate(texts):
        (acc, heard, errs), f = best[i]
        if f != files[i]: shutil.copy(f, files[i])       # winner takes the canonical name
        out.append(files[i]); rows.append({'cau': i + 1, 'acc': round(acc, 3), 'text': t, 'nghe': heard, 'loi': errs})
    return out, rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    c = sp.add_parser('check'); c.add_argument('lines'); c.add_argument('wavdir'); c.add_argument('tag')
    d = sp.add_parser('dict'); d.add_argument('text')
    a = ap.parse_args()
    if a.cmd == 'dict':
        print(apply_dict(a.text, load_dict()))
    else:
        L = json.load(open(a.lines, encoding='utf8'))
        for i, t in enumerate(L):
            acc, heard, errs = score(os.path.join(a.wavdir, f'{a.tag}_{i}.wav'), t if isinstance(t, str) else t[-1])
            print(f'{i + 1:3d} {acc * 100:5.1f}%  {heard}  {errs if acc < 1 else ""}')


if __name__ == '__main__':
    main()
