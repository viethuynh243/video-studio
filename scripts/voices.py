"""Voice catalogue + choosing a voice by PURPOSE (no forced default voice).

  python voices.py profile                     # one-time: synthesise a test passage with every voice, measure
                                               #   accuracy (Whisper), pitch, speaking rate -> ~/.cache/video_studio/voices.json
  python voices.py suggest --muc-dich doanh_nghiep [--gioi-tinh nam] [--vung bac] [--top 5]
  python voices.py purposes                    # list purposes and what they favour

Engines: VieNeu-TTS presets (25 Vietnamese voices, local), Edge TTS (vi-VN-NamMinhNeural, vi-VN-HoaiMyNeural, online),
own recording ("file"), or a clone of a consenting speaker ("clone").
Importable: suggest(muc_dich, gioi_tinh, vung, top) -> [(voice_name, score, reasons)], PURPOSES, catalogue().
"""
import argparse, json, os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.expanduser('~/.cache/video_studio/voices.json')

# purpose -> preferences. style keys come from VieNeu labels: tin tức, kể chuyện, tự nhiên, đọc truyện
# rate = syllables per second INCLUDING natural pauses (measured by `profile` on the TEST passage)
PURPOSES = {
    'doanh_nghiep': {'mo_ta': 'Phim doanh nghiệp, giới thiệu dự án, hồ sơ năng lực', 'style': {'kể chuyện': 3, 'tin tức': 2.5, 'tự nhiên': 1},
                     'pitch': 'tram_vua', 'rate': (3.0, 3.9), 'vung': 'bac'},
    'thoi_su': {'mo_ta': 'Bản tin, thông cáo, tin tức', 'style': {'tin tức': 3, 'kể chuyện': 1}, 'pitch': 'vua', 'rate': (3.2, 4.2), 'vung': 'bac'},
    'tai_lieu': {'mo_ta': 'Phim tài liệu, kể chuyện, lịch sử', 'style': {'kể chuyện': 3, 'đọc truyện': 2}, 'pitch': 'tram', 'rate': (2.6, 3.6)},
    'quang_cao': {'mo_ta': 'Quảng cáo, ra mắt sản phẩm, năng động', 'style': {'tự nhiên': 3, 'tin tức': 1}, 'pitch': 'sang', 'rate': (3.5, 4.6)},
    'mang_xa_hoi': {'mo_ta': 'TikTok/Reels/Shorts, vlog, thân thiện', 'style': {'tự nhiên': 3}, 'pitch': 'sang', 'rate': (3.5, 4.8)},
    'huong_dan': {'mo_ta': 'Hướng dẫn, đào tạo, e-learning', 'style': {'tự nhiên': 2.5, 'tin tức': 2}, 'pitch': 'vua', 'rate': (3.0, 4.0)},
    'sang_trong': {'mo_ta': 'Bất động sản cao cấp, thương hiệu sang', 'style': {'kể chuyện': 3, 'tự nhiên': 1}, 'pitch': 'tram', 'rate': (2.6, 3.5)},
    'tre_em': {'mo_ta': 'Nội dung thiếu nhi, kể chuyện cho bé', 'style': {'đọc truyện': 3, 'kể chuyện': 2}, 'pitch': 'sang', 'rate': (2.8, 3.8),
               'gioi_tinh': 'nu'},
    'su_kien': {'mo_ta': 'Khai mạc, lễ kỷ niệm, vinh danh', 'style': {'tin tức': 2.5, 'kể chuyện': 2.5}, 'pitch': 'tram_vua', 'rate': (3.0, 3.8),
                'vung': 'bac'},
}
EDGE = [{'name': 'edge:vi-VN-NamMinhNeural', 'engine': 'edge', 'gioi_tinh': 'nam', 'vung': 'nam', 'style': 'tin tức'},
        {'name': 'edge:vi-VN-HoaiMyNeural', 'engine': 'edge', 'gioi_tinh': 'nu', 'vung': 'bac', 'style': 'tin tức'}]
TEST = ['Dự án được khởi công vào năm 2024, với tổng mức đầu tư hơn 5.000 tỷ đồng.',
        'Tuyến đường dài 120 km, đi qua bốn tỉnh, rút ngắn thời gian di chuyển xuống còn hai giờ.']


def fold(s):
    import unicodedata
    s = s.lower().replace('đ', 'd')
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def catalogue():
    """VieNeu presets with parsed gender/region/style (+ Edge)."""
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    r = subprocess.run([sys.executable, os.path.join(HERE, 'tts_vi.py'), '--list-json'], capture_output=True, env=env)
    out = []
    for x in json.loads(r.stdout.decode('utf8', 'replace').strip().splitlines()[-1]):
        parts = [p.strip() for p in x['label'].split('—', 1)[-1].split('·')]
        g = 'nu' if parts[0].lower().startswith('nữ') else 'nam'
        vung = {'bắc': 'bac', 'trung': 'trung', 'nam': 'nam'}.get(parts[1].lower(), parts[1].lower()) if len(parts) > 1 else ''
        style = re.sub(r'^(phong cách|giọng đọc)\s*', '', parts[2].lower()) if len(parts) > 2 else ''
        out.append({'name': x['name'], 'engine': 'vieneu', 'gioi_tinh': g, 'vung': vung, 'style': style, 'pick': x['pick']})
    return out + EDGE


def profile(only=None):
    """Synthesise TEST with each voice; measure ASR accuracy, median F0, syllables/s. Cached."""
    import numpy as np, librosa, difflib
    from faster_whisper import WhisperModel
    sys.path.insert(0, HERE); import speech_check as sc
    cat = catalogue(); prof = load_profiles()
    m = WhisperModel('medium', device='cpu', compute_type='int8')
    d = tempfile.mkdtemp(prefix='voices_'); jp = os.path.join(d, 't.json'); json.dump(TEST, open(jp, 'w', encoding='utf8'), ensure_ascii=False)
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    ref = sc.spelled_to_digits(sc.tok(' '.join(TEST)))
    for v in cat:
        if only and v['name'] not in only: continue
        files = synth(TEST, v['name'], d, env=env)
        y = np.concatenate([librosa.load(f, sr=16000)[0] for f in files])
        f0, _, _ = librosa.pyin(y, fmin=60, fmax=400, sr=16000)
        segs, _ = m.transcribe(np.ascontiguousarray(y, dtype=np.float32), language='vi')
        hyp = sc.spelled_to_digits(sc.tok(' '.join(s.text for s in segs)))
        sm = difflib.SequenceMatcher(None, ref, hyp, autojunk=False)
        acc = sum(n for *_, n in sm.get_matching_blocks()) / len(ref)
        sp = len(y) / 16000; syl = sum(len(re.findall(r'\w+', t)) for t in TEST)
        prof[v['name']] = dict(v, acc=round(acc, 3), f0=round(float(np.nanmedian(f0)), 1), rate=round(syl / sp, 2))
        print(f"{v['name']:28s} acc {acc:.3f}  F0 {prof[v['name']]['f0']:6.1f} Hz  {prof[v['name']]['rate']:.2f} âm tiết/s")
        os.makedirs(os.path.dirname(CACHE), exist_ok=True); json.dump(prof, open(CACHE, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    return prof


def load_profiles():
    return json.load(open(CACHE, encoding='utf8')) if os.path.exists(CACHE) else {}


def synth(texts, voice, outdir, env=None, temperature=0.8, suffix='', only=None, tag=None):
    """Synthesise lines with any engine. voice: VieNeu name | 'edge:<ShortName>' | 'clone:<wav>'. Returns wav paths."""
    import unicodedata
    os.makedirs(outdir, exist_ok=True)
    env = env or dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    base = tag or ''.join(c for c in unicodedata.normalize('NFD', voice.replace('đ', 'd').replace('Đ', 'D').split(':')[-1].split('/')[-1].split('\\')[-1])
                          if unicodedata.category(c) != 'Mn' and c.isalnum())
    files = [os.path.join(outdir, f'{base}_{i}{suffix}.wav') for i in range(len(texts))]
    if voice.startswith('edge:'):
        import asyncio, edge_tts
        sys.path.insert(0, HERE); import tts_vi
        for i, t in enumerate(texts):
            if only and i not in only: continue
            mp3 = files[i][:-4] + '.mp3'
            asyncio.run(edge_tts.Communicate(tts_vi.normalize(t), voice[5:]).save(mp3))
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', mp3, '-ar', '48000', '-ac', '1', files[i]], check=True); os.remove(mp3)
        return files
    jp = os.path.join(outdir, f'{base}{suffix}_lines.json'); json.dump(texts, open(jp, 'w', encoding='utf8'), ensure_ascii=False)
    cmd = [sys.executable, os.path.join(HERE, 'tts_vi.py'), jp, outdir, '--tag', base, '--temperature', str(temperature)]
    cmd += ['--ref-audio', voice[6:]] if voice.startswith('clone:') else ['--voices', voice]
    if suffix: cmd += ['--suffix', suffix]
    if only: cmd += ['--only'] + [str(i) for i in only]
    r = subprocess.run(cmd, capture_output=True, env=env)
    if r.returncode: raise RuntimeError(r.stderr.decode('utf8', 'replace')[-1500:])
    return files


def suggest(muc_dich='doanh_nghiep', gioi_tinh=None, vung=None, top=5, tram=None):
    P = PURPOSES[muc_dich]; prof = load_profiles(); cat = prof.values() if prof else catalogue()
    gioi_tinh = gioi_tinh or P.get('gioi_tinh'); vung = vung or P.get('vung')
    res = []
    for v in cat:
        sc, why = 0.0, []
        w = P['style'].get(v['style'], 0); sc += w; why.append(f"phong cách {v['style'] or '?'}")
        if gioi_tinh:
            if v['gioi_tinh'] == gioi_tinh: sc += 2
            else: sc -= 5
        if vung:
            if v['vung'] == vung: sc += 2.5; why.append(f'giọng {vung}')
            else: sc -= 3
        if 'acc' in v:
            sc += (v['acc'] - 0.9) * 30; why.append(f"đọc đúng {v['acc'] * 100:.0f}%")
            if v['acc'] < 0.95: sc -= 4
            lo, hi = P['rate']
            if lo <= v['rate'] <= hi: sc += 1; why.append(f"tốc độ {v['rate']} âm tiết/s hợp")
            f0 = v['f0']; male = v['gioi_tinh'] == 'nam'
            deep = f0 < (115 if male else 200); bright = f0 > (150 if male else 240)
            want = tram or P['pitch']
            if want == 'tram' and deep: sc += 1.5; why.append('giọng trầm')
            if want == 'sang' and bright: sc += 1.5; why.append('giọng sáng')
            if want in ('vua', 'tram_vua') and not bright: sc += 1
        if v.get('pick'): sc += 0.3
        if v['engine'] == 'edge': sc -= 1; why.append('cần mạng')
        res.append((v['name'], round(sc, 2), ', '.join(why)))
    return sorted(res, key=lambda x: -x[1])[:top]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('profile'); p.add_argument('--only', nargs='+')
    s = sp.add_parser('suggest'); s.add_argument('--muc-dich', default='doanh_nghiep', choices=list(PURPOSES))
    s.add_argument('--gioi-tinh', choices=['nam', 'nu']); s.add_argument('--vung', choices=['bac', 'trung', 'nam'])
    s.add_argument('--top', type=int, default=5); s.add_argument('--tram', choices=['tram', 'vua', 'sang'])
    sp.add_parser('purposes')
    a = ap.parse_args()
    if a.cmd == 'profile': profile(a.only)
    elif a.cmd == 'purposes':
        for k, v in PURPOSES.items(): print(f"{k:13s} {v['mo_ta']}  | phong cách ưu tiên: {', '.join(v['style'])}")
    else:
        if not load_profiles(): print('(chưa có hồ sơ đo - chạy `voices.py profile` một lần để xếp hạng theo độ chính xác)')
        for n, sc, why in suggest(a.muc_dich, a.gioi_tinh, a.vung, a.top, a.tram): print(f'{sc:6.2f}  {n:28s} {why}')


if __name__ == '__main__':
    main()
