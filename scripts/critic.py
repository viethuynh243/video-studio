"""Independent critique kit: everything a fresh reviewer (judge != builder) needs to score a cut, plus hard checks.

  python critic.py FILM.mp4 [--project project.json] [--facts facts.md] [--out DIR] [--hold 1.0]

Writes to DIR (default <film>_critic/):
  contact.png   2 fps overview (6 x N grid)        phone.png  1 fps at 360 px wide (readability on a phone)
  strip_*.png   12 frames around each fast move    CRITIC.md  hard-check results + the scoring rubric to fill in
Hard checks:
  - dead frames: picture frozen longer than --hold seconds (except the final hold), measured on the image
  - on-screen text from the project shown long enough (>= 0.3 s per word, >= 1.5 s total) and no em dash
  - every number in on-screen text / narration exists in facts.md (sourced figures only)
  - loudness / true peak, black stretches, stray frames (from probe_qc)
The reviewer (a separate read-only agent, default verdict = REJECT) then scores 1-10 per category, lists the
3 worst problems with timestamps, and does the muted test: describe the film in one sentence from the frames alone.
"""
import argparse, json, os, re, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from probe_qc import qc, probe  # noqa: E402

RUBRIC = """## Chấm điểm (người chấm độc lập điền - mặc định "SỬA THÊM")

| Hạng mục | Điểm /10 | Ghi chú |
|---|---|---|
| Mở đầu 3 giây (hình mạnh nhất, khung đầu đẹp ngay) | | |
| Câu chuyện rõ, đúng sự thật (đúng công trình, số liệu có nguồn) | | |
| Nhịp (cắt đúng lời/phách, không lê thê, không khung chết) | | |
| Chuyển động (mượt, có ease, một chuyển động mỗi shot, không giật) | | |
| Hình ảnh (nét, màu khớp, bố cục, không logo/QR/chữ lạ) | | |
| Chữ & phụ đề (đọc được ở điện thoại, đủ lâu, không che hình quan trọng) | | |
| Âm thanh (giọng rõ, đúng phát âm, nhạc không lấn, chuyển mượt) | | |
| Đồng bộ (chữ/hình xuất hiện đúng lúc lời nói tới) | | |

**Thử tắt tiếng**: chỉ nhìn contact.png + phone.png, viết MỘT câu tóm tắt phim. Không viết được -> trượt.
**3 lỗi nặng nhất** (mốc thời gian, mức độ, cách sửa đo được):
1.
2.
3.

Kết luận: ĐẠT (mọi hạng mục >= 8) / SỬA THÊM. Chỉ sửa hạng mục <= 7, không đụng hạng mục >= 9.
"""


def ff(args):
    subprocess.run(['ffmpeg', '-v', 'error', '-y'] + args, check=True)


def dead_frames(path, hold, fps):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-an', '-vf', 'scale=96:54,format=gray', '-f', 'rawvideo', '-'],
                         capture_output=True).stdout
    G = np.frombuffer(raw, np.uint8).reshape(-1, 54, 96).astype(np.float32)
    d = np.abs(np.diff(G, axis=0)).mean((1, 2)) if len(G) > 1 else np.zeros(0)
    still = d < 0.04          # truly frozen; slow drift/zoom gives ~0.1
    out, run = [], 0
    for i, s in enumerate(still):
        run = run + 1 if s else 0
        if run == int(hold * fps): out.append(round((i - run + 1) / fps, 2))
    total = len(G) / fps
    return [t for t in out if t < total - 1.5]          # the final hold is allowed


def numbers(s):
    return set(re.findall(r'\d+(?:[.,]\d+)*', s or ''))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('film'); ap.add_argument('--project'); ap.add_argument('--facts'); ap.add_argument('--out')
    ap.add_argument('--hold', type=float, default=1.0)
    a = ap.parse_args()
    out = a.out or os.path.splitext(a.film)[0] + '_critic'; os.makedirs(out, exist_ok=True)
    info = probe(a.film); fps = info['fps'] or 25; dur = info['duration']
    rows = int(np.ceil(dur * 2 / 6))
    ff(['-i', a.film, '-vf', f'fps=2,scale=320:-1,tile=6x{rows}', '-frames:v', '1', os.path.join(out, 'contact.png')])
    ff(['-i', a.film, '-vf', f'fps=1,scale=360:-1,tile=5x{int(np.ceil(dur / 5))}', '-frames:v', '1', os.path.join(out, 'phone.png')])
    r = qc(a.film, True)
    fast = sorted([s for s in r['shots'] if (s.get('motion') or 0) > 3], key=lambda s: -(s.get('motion') or 0))[:3]
    for k, s in enumerate(fast):
        t = max(0, (s['start'] + s['end']) / 2 - 0.25)
        ff(['-ss', f'{t:.2f}', '-i', a.film, '-vf', 'scale=320:-1,tile=12x1', '-frames:v', '12', '-update', '1',
            os.path.join(out, f'strip_{k + 1}_{t:.1f}s.png')])
    lines = [f'# Phê bình độc lập - {os.path.basename(a.film)}', '', f'{info["width"]}x{info["height"]} · {fps} fps · {dur:.2f} s', '',
             '## Kiểm tra cứng']
    plan_p = os.path.splitext(a.film)[0] + '_plan.json'
    planned = json.load(open(plan_p, encoding='utf8')) if os.path.exists(plan_p) else []
    inside = lambda t: any(x[0] - 0.1 <= t <= x[1] + 0.1 for x in planned)
    s = r['summary']; errs = [f for f in r['findings'] if f['type'] not in ('long_shot',) and not inside(f.get('t', -9))]
    if planned: lines_planned = sum(1 for f in r['findings'] if f['type'] != 'long_shot' and inside(f.get('t', -9)))
    lines.append(f'- Lỗi hình (khung lạc, chớp, đoạn đen, đứng hình): **{len(errs)}** {errs if errs else ""}')
    if planned: lines.append(f'- Thay đổi hình trong chuyển cảnh/thẻ đã lên kế hoạch: {lines_planned} (không tính lỗi; xem bằng mắt có đẹp không)')
    lines.append(f'- Độ giật trung vị {s["judder_median"]}, p90 {s["judder_p90"]}; nhịp khung lệch: {s["uneven_cadence_shots"]} shot')
    lines.append(f'- Âm lượng {s.get("I_LUFS")} LUFS, True Peak {s.get("TP_dBFS")} dBFS')
    dead = [t for t in dead_frames(a.film, a.hold, fps) if not any(x[0] - 0.1 <= t <= x[1] and x[2] in ('fade_black',) for x in planned)]
    lines.append(f'- Khung chết > {a.hold:g} s (trừ khung giữ cuối): **{len(dead)}** {dead if dead else ""}')
    if a.project:
        P = json.load(open(a.project, encoding='utf8')); C = P.get('canh', [])
        facts = open(a.facts, encoding='utf8').read() if a.facts else ''
        fact_nums = numbers(facts)
        for c in C:
            txt = c.get('chu_tren_hinh') or ''
            if '—' in txt + (c.get('thoai') or ''): lines.append(f'- {c["id"]}: có gạch dài "—"')
            if txt:
                need = max(1.5, 0.3 * len(txt.split()))
                if c.get('thoi_luong') and float(c['thoi_luong']) < need:
                    lines.append(f'- {c["id"]}: chữ "{txt}" cần >= {need:.1f} s trên hình')
            if a.facts:
                miss = (numbers(txt) | numbers(c.get('thoai'))) - fact_nums
                if miss: lines.append(f'- {c["id"]}: số **chưa có nguồn** trong facts.md: {sorted(miss)}')
        if not a.facts and any(numbers(c.get('chu_tren_hinh')) for c in C):
            lines.append('- Có số liệu trên hình nhưng chưa có facts.md (mỗi con số + câu gốc + nguồn + ngày) -> chưa được giao')
    lines += ['', '## Tư liệu cho người chấm', '- contact.png, phone.png, ' + ', '.join(os.path.basename(f) for f in os.listdir(out) if f.startswith('strip_')), '', RUBRIC]
    open(os.path.join(out, 'CRITIC.md'), 'w', encoding='utf8').write('\n'.join(lines))
    print('\n'.join(lines[:12])); print('->', out)


if __name__ == '__main__':
    main()
