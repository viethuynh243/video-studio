"""Check a voice track against the approved script: word accuracy (faster-whisper) + optional dialect estimate.

  python speech_check.py VOICE.wav [VOICE2.wav ...] --ref script.txt|script.json [--dialect] [--model medium]

Run it on the VOICE STEM, not on the final mix (music-only passages make Whisper invent words).
Accuracy compares toned words after light normalisation (numbers vs words: "bốn"->4, "ki lô mét"->km).
--dialect uses thangtrungnguyen/vietnamese-regional-accent-classification-model (downloaded once to
~/.cache/accent_vi). Treat its output as a hint only: it is unreliable on synthetic voices.
"""
import argparse, difflib, json, os, re, subprocess, sys

NUM = {'không': '0', 'một': '1', 'hai': '2', 'ba': '3', 'bốn': '4', 'năm': '5', 'sáu': '6', 'bảy': '7', 'tám': '8', 'chín': '9'}


def tok(s):
    s = s.lower().replace('km/h', 'km trên giờ').replace('ki lô mét', 'km').replace('ki-lô-mét', 'km').replace('kilômét', 'km').replace('kilomet', 'km')
    s = re.sub(r'(?<=\d)[.,](?=\d{3}(?!\d))', '', s)          # 1.200 -> 1200 (thousands separator)
    s = re.sub(r'(\d)([^\W\d_])', r'\1 \2', s)            # 1200m -> 1200 m
    s = re.sub(r'[^\w\s]', ' ', s)
    out = []
    for w in s.split():
        out.append(NUM.get(w, w))
    # collapse spelled numbers like "một trăm mười chín" crudely: keep as words; digits from ASR are split to digits
    res = []
    for w in out:
        if w.isdigit() and len(w) > 1: res.extend(list(w))
        else: res.append(w)
    return res


def load_ref(p):
    if p.endswith('.json'):
        d = json.load(open(p, encoding='utf8'))
        return ' '.join(x if isinstance(x, str) else (x['text'] if isinstance(x, dict) else x[2]) for x in d)
    return open(p, encoding='utf8').read()


def spelled_to_digits(words):
    """'1 trăm mười 9' -> '119' style collapse so ASR digits and spelled numbers compare equal."""
    unit = {'trăm': 100, 'mươi': 10, 'mười': 10}
    out, i = [], 0
    while i < len(words):
        w = words[i]
        if w.isdigit() or w in ('trăm', 'mươi', 'mười', 'linh', 'lẻ'):
            j, val, cur = i, 0, 0
            while j < len(words) and (words[j].isdigit() or words[j] in ('trăm', 'mươi', 'mười', 'linh', 'lẻ')):
                x = words[j]
                if x.isdigit(): cur = cur * 10 + int(x) if cur and words[j - 1].isdigit() else cur + int(x)
                elif x == 'trăm': val += (cur or 1) * 100; cur = 0
                elif x == 'mười': cur += 10
                elif x == 'mươi': cur = (cur or 1) * 10
                j += 1
            out.append(str(val + cur)); i = j
        else:
            out.append(w); i += 1
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('files', nargs='+'); ap.add_argument('--ref', required=True)
    ap.add_argument('--dialect', action='store_true'); ap.add_argument('--model', default='medium')
    ap.add_argument('--device', default='cpu')
    a = ap.parse_args()
    from faster_whisper import WhisperModel
    m = WhisperModel(a.model, device=a.device, compute_type='int8' if a.device == 'cpu' else 'float16')
    ref = spelled_to_digits(tok(load_ref(a.ref)))
    for f in a.files:
        segs, _ = m.transcribe(f, language='vi', beam_size=5, vad_filter=True)
        hyp_text = ' '.join(s.text.strip() for s in segs)
        hyp = spelled_to_digits(tok(hyp_text))
        sm = difflib.SequenceMatcher(None, ref, hyp, autojunk=False)
        acc = sum(n for *_, n in sm.get_matching_blocks()) / max(1, len(ref))
        errs = [(' '.join(ref[a1:a2]), ' '.join(hyp[b1:b2])) for op, a1, a2, b1, b2 in sm.get_opcodes() if op != 'equal']
        print(f'== {os.path.basename(f)}  accuracy {acc:.3f}  ({len(ref)} ref words)')
        print('   ASR:', hyp_text)
        for e in errs: print(f'   ref "{e[0]}" -> heard "{e[1]}"')
    if a.dialect:
        md = os.path.expanduser('~/.cache/accent_vi')
        if not os.path.exists(os.path.join(md, 'model.safetensors')):
            os.makedirs(md, exist_ok=True)
            for fn in ('config.json', 'preprocessor_config.json', 'model.safetensors'):
                subprocess.run(['curl', '-sL', '-o', os.path.join(md, fn),
                                f'https://huggingface.co/thangtrungnguyen/vietnamese-regional-accent-classification-model/resolve/main/{fn}'])
        import torch, librosa, numpy as np
        from transformers import Wav2Vec2ForSequenceClassification, Wav2Vec2FeatureExtractor
        fe = Wav2Vec2FeatureExtractor.from_pretrained(md); cm = Wav2Vec2ForSequenceClassification.from_pretrained(md).eval()
        lab = cm.config.id2label
        for f in a.files:
            y, _ = librosa.load(f, sr=16000); y, _ = librosa.effects.trim(y, top_db=35)
            ps = []
            with torch.no_grad():
                for s in range(0, max(1, len(y) - 16000 * 3), 16000 * 2):
                    ps.append(torch.softmax(cm(**fe(y[s:s + 64000], sampling_rate=16000, return_tensors='pt')).logits, -1)[0].numpy())
            p = np.mean(ps, 0)
            print(f'   dialect {os.path.basename(f)}: ' + ', '.join(f'{lab[i].split()[0]}={p[i]:.2f}' for i in range(len(p))))


if __name__ == '__main__':
    main()
