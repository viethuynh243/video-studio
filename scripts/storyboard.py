"""Storyboard JSON tools (template: ../templates/storyboard.json).

  python storyboard.py check  SB.json                # validate fields, durations vs speech length, missing sources
  python storyboard.py shotlist SB.json [--csv out.csv]   # Markdown/CSV shot list for the crew / editor
  python storyboard.py script SB.json out.json        # [[start, end, text], ...] for tts_vi.py / voice_mix.py
  python storyboard.py jobs SB.json out_jobs.json     # one job per scene for an AI render queue (ComfyUI etc.)

Speech-rate check: Vietnamese formal narration ~4.5-5.5 syllables/s; a scene whose line needs more than its
duration at 5.5 syll/s is flagged.
"""
import argparse, csv, json, os, re, sys

CO_CANH = {'ECU', 'CU', 'MCU', 'MS', 'MWS', 'WS', 'EWS', 'INSERT'}
CHUYEN_DONG = {'static', 'pan', 'tilt', 'push_in', 'pull_out', 'truck', 'pedestal', 'orbit', 'reveal', 'tracking',
               'handheld', 'zoom', 'hyperlapse', 'timelapse', 'ken_burns', 'animation'}
REQ = ['id', 'thoi_luong', 'co_canh', 'goc_may', 'chuyen_dong', 'boi_canh']


def syll(t):
    return len(re.findall(r'\w+', t or ''))


def load(p):
    return json.load(open(p, encoding='utf8'))


def check(sb):
    errs, warn, t = [], [], 0.0
    ids = set()
    for c in sb['canh']:
        for k in REQ:
            if c.get(k) in (None, ''): errs.append(f'{c.get("id")}: thiếu "{k}"')
        if c['id'] in ids: errs.append(f'{c["id"]}: trùng id')
        ids.add(c['id'])
        if c.get('co_canh') and c['co_canh'].upper() not in CO_CANH: warn.append(f'{c["id"]}: cỡ cảnh lạ "{c["co_canh"]}"')
        if c.get('chuyen_dong') and c['chuyen_dong'] not in CHUYEN_DONG: warn.append(f'{c["id"]}: chuyển động lạ "{c["chuyen_dong"]}"')
        need = syll(c.get('thoai')) / 5.5
        if need > c.get('thoi_luong', 0) + 0.01:
            errs.append(f'{c["id"]}: lời {syll(c.get("thoai"))} âm tiết cần ~{need:.1f}s > {c["thoi_luong"]}s')
        if c.get('thoi_luong', 0) > 8 and c.get('chuyen_dong') != 'animation': warn.append(f'{c["id"]}: cảnh dài {c["thoi_luong"]}s (>8s)')
        n = c.get('nguon')
        if n and n.get('file') and not os.path.exists(n['file']): errs.append(f'{c["id"]}: không thấy nguồn {n["file"]}')
        if re.search(r'—', c.get('chu_tren_hinh', '') + c.get('thoai', '')): warn.append(f'{c["id"]}: có gạch dài "—"')
        for nv in c.get('nhan_vat', []):
            if nv not in sb.get('nhan_vat', {}): errs.append(f'{c["id"]}: nhân vật "{nv}" chưa khai báo')
        t += c.get('thoi_luong', 0)
    return errs, warn, t


def timeline(sb):
    t, out = 0.0, []
    for c in sb['canh']:
        out.append((round(t, 2), round(t + c['thoi_luong'], 2), c)); t += c['thoi_luong']
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['check', 'shotlist', 'script', 'jobs']); ap.add_argument('sb'); ap.add_argument('out', nargs='?')
    ap.add_argument('--csv')
    a = ap.parse_args()
    sb = load(a.sb)
    if a.cmd == 'check':
        e, w, t = check(sb)
        print(f'{len(sb["canh"])} cảnh, tổng {t:.1f}s; {len(e)} lỗi, {len(w)} cảnh báo')
        for x in e: print('  LỖI', x)
        for x in w: print('  chú ý', x)
        sys.exit(1 if e else 0)
    tl = timeline(sb)
    if a.cmd == 'shotlist':
        cols = ['id', 'vao', 'ra', 'co_canh', 'goc_may', 'chuyen_dong', 'boi_canh', 'hanh_dong', 'thoai', 'chu_tren_hinh', 'chuyen_canh', 'trang_thai']
        rows = [[c['id'], s, e, c.get('co_canh'), c.get('goc_may'), c.get('chuyen_dong'), c.get('boi_canh'), c.get('hanh_dong', ''),
                 c.get('thoai', ''), c.get('chu_tren_hinh', ''), c.get('chuyen_canh', ''), c.get('trang_thai', '')] for s, e, c in tl]
        print('| ' + ' | '.join(cols) + ' |\n|' + '---|' * len(cols))
        for r in rows: print('| ' + ' | '.join(str(x) for x in r) + ' |')
        if a.csv:
            with open(a.csv, 'w', newline='', encoding='utf-8-sig') as f: w = csv.writer(f); w.writerow(cols); w.writerows(rows)
    elif a.cmd == 'script':
        json.dump([[s, e, c['thoai']] for s, e, c in tl if c.get('thoai')], open(a.out, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
        print('wrote', a.out)
    else:
        jobs = []
        for s, e, c in tl:
            chars = [sb['nhan_vat'][n] for n in c.get('nhan_vat', [])]
            prompt = ', '.join(x for x in [c.get('co_canh'), c.get('goc_may'), f"camera {c.get('chuyen_dong')}", c.get('boi_canh'),
                                           c.get('hanh_dong'), c.get('cam_xuc'), *[ch.get('trang_phuc', '') for ch in chars],
                                           c.get('prompt_bo_sung')] if x)
            jobs.append({'id': c['id'], 'duration': c['thoi_luong'], 'fps': sb.get('fps', 24), 'prompt': prompt,
                         'ref_images': sum([ch.get('anh_tham_chieu', []) for ch in chars], []),
                         'lora': [ch.get('lora') for ch in chars if ch.get('lora')], 'seed': c.get('seed'),
                         'dialogue': c.get('thoai', ''), 'voice': (chars[0].get('giong') if chars else sb.get('giong_mac_dinh')),
                         'lipsync': bool(chars) and c.get('loai_thoai') == 'thoai' and c.get('co_canh') in ('CU', 'MCU', 'MS'),
                         'status': 'pending', 'attempts': 0})
        json.dump(jobs, open(a.out, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
        print('wrote', len(jobs), 'jobs ->', a.out)


if __name__ == '__main__':
    main()
