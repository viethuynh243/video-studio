"""Anti "AI slop" guard: deterministic checks first (no LLM, repeatable), Claude review only for what is flagged.

  python slop_guard.py script  SCRIPT(.txt|.json|project.json) [--facts facts.md brief.txt ...] [--lang vi|en] [--json out.json]
  python slop_guard.py project PROJECT.json [--facts ...] [--rules RULES.json ...]        # script + edit decisions + client rules
  python slop_guard.py rules   RULES.json [--project PROJECT.json]                         # rule ledger status (coverage, stale)
  python slop_guard.py review  PROJECT.json OUT_DIR [--facts ...] [--rules ...]           # SLOP_REVIEW.md for a fresh reviewer
  python slop_guard.py compare BEFORE.json AFTER.json                                      # accept a rewrite only if nothing got worse
  python slop_guard.py ghi     RULES.json --nguon "câu sửa nguyên văn" --loai cam_chu --mau "regex" [--pham-vi khach:X] [--muc chan]

Design (patterns, re-implemented here):
  * System 0 = deterministic metrics, kept SEPARATE (never one blended score), each finding has a level
    (chan = must fix / canh_bao = warn / ghi_chu = note) and a reason. Nothing is rewritten silently.
  * Grounding ledger: every number in narration / on-screen text must be found in the fact sources, or be derivable
    from grounded numbers (unit conversion, sum, difference, product, ratio, percentage) or shown as [tính: a × b = c].
  * Client rule ledger: past corrections are stored verbatim with scope + date and checked deterministically on
    every new film (keep the ledger OUTSIDE public repos, e.g. ~/.video_studio/luat/<khach>.json).
  * System 2 (Claude) only gets the flagged items, as a blind reviewer that proposes rewrites; the rewrite is then
    re-measured by System 0 and accepted only if no metric gets worse. The detector never certifies its own fix.
"""
import argparse, json, math, os, re, sys, unicodedata
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- lexicons (own lists; extend per project)
CLICHE_VI = [
    'trong bối cảnh', 'hành trình', 'kiến tạo', 'vươn tầm', 'tầm cao mới', 'khẳng định vị thế', 'dấu ấn',
    'bước tiến vượt bậc', 'bước ngoặt', 'đột phá', 'không ngừng nỗ lực', 'chung tay', 'góp phần quan trọng', 'đóng vai trò then chốt',
    'đóng vai trò quan trọng', 'mở ra kỷ nguyên', 'kỷ nguyên mới', 'đầy tiềm năng', 'hơn bao giờ hết', 'trong thời đại',
    'thế giới ngày nay', 'không thể phủ nhận', 'có thể nói', 'hãy cùng', 'cùng khám phá', 'sứ mệnh cao cả', 'tầm nhìn chiến lược',
    'phát triển vượt bậc', 'đỉnh cao', 'vô cùng quan trọng', 'hết sức quan trọng', 'ý nghĩa to lớn', 'niềm tự hào', 'tự hào là',
    'không ngừng đổi mới', 'sáng tạo không ngừng', 'đồng hành cùng', 'chặng đường', 'viết tiếp', 'nâng tầm', 'cất cánh',
    'trái tim', 'linh hồn', 'diện mạo mới', 'bức tranh', 'thắp sáng', 'lan toả',
]
FILLER_VI = ['thực sự', 'một cách', 'vô cùng', 'hết sức', 'rất là', 'đặc biệt là', 'nói chung', 'về cơ bản', 'có thể thấy', 'rõ ràng là']
CLICHE_EN = [
    'delve', 'tapestry', 'testament to', 'seamless', 'unlock', 'elevate', 'in today\'s fast-paced', 'game-changer', 'game changer',
    'cutting-edge', 'revolutionize', 'embark', 'journey', 'realm', 'harness', 'pivotal', 'robust', 'synergy', 'whether you\'re',
    'it\'s worth noting', 'in conclusion', 'ever-evolving', 'landscape', 'paradigm', 'empower', 'leverage', 'navigate the',
]
SUPERLATIVE_VI = ['hàng đầu', 'tốt nhất', 'lớn nhất', 'dài nhất', 'cao nhất', 'đầu tiên', 'duy nhất', 'số 1', 'số một', 'vượt trội',
                  'tiên phong', 'chưa từng có', 'kỷ lục', 'xuất sắc nhất', 'hiện đại nhất']
SUPERLATIVE_EN = ['leading', 'best', 'largest', 'first', 'only', 'number one', 'unrivalled', 'unmatched', 'world-class', 'record']
UNITS = {('km', 'm'): 1000, ('m', 'cm'): 100, ('tỷ', 'triệu'): 1000, ('triệu', 'nghìn'): 1000, ('ha', 'm2'): 10000, ('giờ', 'phút'): 60}


def nfc(s): return unicodedata.normalize('NFC', s or '')


def sentences(text):
    return [s.strip() for s in re.split(r'(?<=[.!?…])\s+|\n+', nfc(text)) if len(s.strip()) > 2]


def words(s): return re.findall(r'\w+', s.lower())


def num_values(s):
    """Numbers as floats: '1.200' -> 1200 (VN thousands), '3,5' -> 3.5, '2021' -> 2021."""
    out = []
    for m in re.finditer(r'\d+(?:[.,]\d+)*', s):
        t = m.group(0)
        if re.fullmatch(r'\d{1,3}(?:\.\d{3})+', t): v = float(t.replace('.', ''))
        elif re.fullmatch(r'\d+,\d+', t): v = float(t.replace(',', '.'))
        elif re.fullmatch(r'\d{1,3}(?:,\d{3})+', t): v = float(t.replace(',', ''))
        else:
            try: v = float(t.replace(',', '.'))
            except ValueError: continue
        out.append(v)
    return out


# ---------------------------------------------------------------- grounding
def load_facts(paths):
    txt = ''
    for p in paths or []:
        if p.lower().endswith('.docx'):
            try:
                import docx
                txt += '\n'.join(par.text for par in docx.Document(p).paragraphs) + '\n'
            except Exception as e:
                print(f'(không đọc được {p}: {e})', file=sys.stderr)
        else:
            txt += open(p, encoding='utf8', errors='replace').read() + '\n'
    return nfc(txt)


COMMON = (2, 3, 4, 5, 7, 10, 12, 24, 30, 60, 100, 365, 1000)       # constants allowed as calculation operands


def fmt(x): return f'{x:g}'


def grounding(v, base):
    """('nguon', why) if v is in the sources (0.5 % rounding allowed),
       ('suy_ra', why) if it only follows from one step (unit conversion, + - x /, %) on grounded numbers,
       (None, '') otherwise. Derived numbers are SUSPECTED, not certain: they are shown with the derivation for a human."""
    if not base: return None, ''
    B = sorted(set(base))
    for b in B:
        if abs(v - b) <= 1e-9 * max(1, abs(b)): return 'nguon', fmt(b)
    sig = len(re.sub(r'^0+|\.', '', fmt(v)).rstrip('0')) or 1    # a rounded figure may cite a more precise source
    if sig <= 3 and not (v == int(v) and 1900 <= v <= 2100):     # years are never rounded
        for b in B:
            if b and abs(float(f'{b:.{sig}g}') - v) <= 1e-9 * max(1, abs(v)): return 'nguon', f'{fmt(b)} (làm tròn)'
    eq = lambda a, b: abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))
    B2 = B[:300]; found = []
    for i, x in enumerate(B2):                                      # parts of a total first (most natural derivation)
        for y in B2[i + 1:]:
            if eq(v, x + y): found.append(f'{fmt(x)} + {fmt(y)}')
            if eq(v, y - x): found.append(f'{fmt(y)} - {fmt(x)}')
    for k in (10, 100, 1000, 60, 3600, 1e6, 1e9):
        for b in B:
            if eq(v, b * k): found.append(f'{fmt(b)} x {fmt(k)} (đổi đơn vị?)')
            if eq(v, b / k): found.append(f'{fmt(b)} / {fmt(k)} (đổi đơn vị?)')
    for i, x in enumerate(B2):
        for y in B2[i + 1:]:
            for r, why in ((x * y, f'{fmt(x)} x {fmt(y)}'), (y / x if x else None, f'{fmt(y)} / {fmt(x)}'),
                           (x / y * 100 if y else None, f'{fmt(x)} / {fmt(y)} = %')):
                if r is not None and eq(v, r): found.append(why)
    if found: return 'suy_ra', ' | '.join(found[:3]) + (f' (+{len(found) - 3} cách khác - dễ trùng ngẫu nhiên)' if len(found) > 3 else '')
    return None, ''


def grounded(v, base): return grounding(v, base)[0] is not None


def shown_calcs(text, base=None):
    """[tính: 2 × 60 = 120] -> verify the declared calculation (and, with base, that every operand is grounded)."""
    bad, ok = [], []
    for m in re.finditer(r'\[tính:\s*([^\]=]+)=\s*([\d.,]+)\s*\]', text):
        expr, res = m.group(1), num_values(m.group(2))
        e = expr.replace('×', '*').replace('x', '*').replace('÷', '/').replace('−', '-').replace('–', '-').replace(':', '/')
        e = re.sub(r'(?<=\d)\.(?=\d{3}(?!\d))', '', e).replace(',', '.')
        try:
            val = eval(re.sub(r'[^0-9.+\-*/() ]', '', e), {'__builtins__': {}})
            right = bool(res) and abs(val - res[0]) <= 1e-6 * max(1, abs(val))
            loose = [x for x in num_values(expr) if base is not None and x not in COMMON and grounding(x, base)[0] != 'nguon']
            if not right: bad.append((m.group(0), 'phép tính sai'))
            elif loose: bad.append((m.group(0), 'toán hạng không có nguồn: ' + ', '.join(fmt(x) for x in loose)))
            else: ok.append(res[0])
        except Exception:
            bad.append((m.group(0), 'không đọc được phép tính'))
    return ok, bad


# ---------------------------------------------------------------- script metrics (separate, never blended)
def script_findings(lines, facts_txt='', lang='vi'):
    """lines: [(where, text)] where = scene id / line number. Returns (metrics, findings)."""
    F, M = [], {}
    text = '\n'.join(t for _, t in lines)
    sents = [(w, s) for w, t in lines for s in sentences(t)]
    nw = max(1, sum(len(words(s)) for _, s in sents))
    cl, fi, su = (CLICHE_VI, FILLER_VI, SUPERLATIVE_VI) if lang == 'vi' else (CLICHE_EN, [], SUPERLATIVE_EN)
    base = num_values(facts_txt)
    n_cl = n_fi = 0
    for w, s in sents:
        low = s.lower()
        hits = sorted({c for c in cl if c in low}); n_cl += len(hits)
        if hits: F.append({'muc': 'canh_bao', 'loai': 'sao_rong', 'o': w, 'cau': s, 'chi_tiet': hits,
                           'goi_y': 'thay bằng dữ kiện cụ thể (ai, cái gì, bao nhiêu, ở đâu) hoặc bỏ'})
        fh = [f for f in fi if f in low]; n_fi += len(fh)
        if fh: F.append({'muc': 'ghi_chu', 'loai': 'tu_dem', 'o': w, 'cau': s, 'chi_tiet': fh, 'goi_y': 'xoá từ đệm, câu ngắn và chắc hơn'})
        sh = [x for x in su if re.search(r'(?<!\w)' + re.escape(x) + r'(?!\w)', low)]
        if sh:
            nums = num_values(s)
            if not nums or (facts_txt and not all(grounded(v, base) for v in nums)):
                F.append({'muc': 'chan' if facts_txt else 'canh_bao', 'loai': 'khang_dinh_khong_nguon', 'o': w, 'cau': s, 'chi_tiet': sh,
                          'goi_y': 'khẳng định so sánh nhất phải có nguồn (giải thưởng, số liệu, đơn vị công nhận) - không có thì viết lại trung tính'})
        if '—' in s:
            F.append({'muc': 'canh_bao', 'loai': 'gach_dai', 'o': w, 'cau': s, 'goi_y': 'thay "—" bằng dấu phẩy / hai chấm / tách câu'})
        if re.search(r'không chỉ\b.*\bmà còn', low) or re.search(r'not only\b.*\bbut also', low):
            F.append({'muc': 'ghi_chu', 'loai': 'khuon_cau', 'o': w, 'cau': s, 'goi_y': 'khuôn "không chỉ... mà còn" dùng tối đa 1 lần/phim'})
    # numbers must be grounded: in the sources (certain), derived in one step (suspected, shown), or a verified [tính: ...]
    ok_c = []
    for w, s in sents:                                   # per sentence, so a reviewer sees where the calculation is
        ok1, bad1 = shown_calcs(s, base if facts_txt else None); ok_c += ok1
        for b, why in bad1: F.append({'muc': 'chan', 'loai': 'phep_tinh_sai', 'o': w, 'cau': s, 'chi_tiet': [b, why], 'goi_y': 'sửa phép tính hoặc thêm nguồn cho toán hạng'})
    if facts_txt:
        n_all = n_src = n_der = 0
        for w, s in sents:
            for v in num_values(re.sub(r'\[tính:[^\]]*\]', '', s)):
                n_all += 1
                kind, why = grounding(v, base)
                if kind != 'nguon' and '[tính:' in s and any(abs(v - c) <= 1e-6 * max(1, abs(c)) for c in ok_c): kind, why = 'suy_ra', 'phép tính khai báo'
                if kind == 'nguon':
                    n_src += 1
                    if why.endswith('(làm tròn)'):
                        F.append({'muc': 'ghi_chu', 'loai': 'so_lam_tron', 'o': w, 'cau': s, 'chi_tiet': [fmt(v), why],
                                  'goi_y': 'số làm tròn từ nguồn - xác nhận đúng là cùng một số liệu'})
                elif kind == 'suy_ra':
                    n_der += 1
                    if why != 'phép tính khai báo':
                        F.append({'muc': 'ghi_chu', 'loai': 'so_suy_ra', 'o': w, 'cau': s, 'chi_tiet': [fmt(v), why],
                                  'goi_y': 'số không có nguyên văn trong nguồn, chỉ khớp một phép suy - xác nhận đúng phép đó, nếu đúng thì ghi [tính: ...]'})
                else:
                    F.append({'muc': 'chan', 'loai': 'so_khong_nguon', 'o': w, 'cau': s, 'chi_tiet': [fmt(v)],
                              'goi_y': 'thêm nguồn vào facts (câu gốc + tài liệu + ngày) hoặc khai [tính: ...] hoặc bỏ số'})
        M['so_co_nguon'] = f'{n_src}/{n_all} nguyên văn, {n_der} suy ra, {n_all - n_src - n_der} không nguồn'
    else:
        M['so_co_nguon'] = 'chưa có facts - chưa kiểm được'
    # structure / rhythm
    lens = [len(words(s)) for _, s in sents]
    if len(lens) >= 4:
        mu = sum(lens) / len(lens); sd = math.sqrt(sum((x - mu) ** 2 for x in lens) / len(lens)); cv = sd / mu if mu else 0
        M['do_dao_dong_cau'] = round(cv, 2)
        if cv < 0.22: F.append({'muc': 'canh_bao', 'loai': 'nhip_deu_may', 'o': '-', 'cau': f'{len(lens)} câu dài gần như nhau (CV {cv:.2f})',
                                'goi_y': 'xen câu ngắn 4-6 chữ để nhấn và câu dài để kể'})
    openers = {}
    for w, s in sents:
        k = ' '.join(words(s)[:2])
        if k: openers.setdefault(k, []).append(w)
    rep = {k: v for k, v in openers.items() if len(v) >= 3}
    for k, v in rep.items():
        F.append({'muc': 'canh_bao', 'loai': 'mo_dau_lap', 'o': ','.join(map(str, v)), 'cau': f'"{k}..." mở đầu {len(v)} câu', 'goi_y': 'đổi cách vào câu'})
    M['sao_rong_moi_100_chu'] = round(100 * n_cl / nw, 2); M['tu_dem_moi_100_chu'] = round(100 * n_fi / nw, 2); M['so_cau'] = len(sents)
    return M, F


# ---------------------------------------------------------------- edit-decision metrics
def edit_findings(P):
    C = P.get('canh', []); F, M = [], {}
    if len(C) < 3: return M, F
    dur = [float(c.get('thoi_luong') or 0) for c in C if c.get('thoi_luong')]
    if len(dur) >= 4:
        mu = sum(dur) / len(dur); cv = math.sqrt(sum((d - mu) ** 2 for d in dur) / len(dur)) / mu if mu else 0
        M['do_dao_dong_canh'] = round(cv, 2)
        if cv < 0.12: F.append({'muc': 'canh_bao', 'loai': 'canh_dai_deu', 'o': '-', 'cau': f'các cảnh dài gần bằng nhau (CV {cv:.2f})', 'goi_y': 'nhịp theo nội dung, không chia đều'})
    trans = [c.get('chuyen_canh', 'cut') for c in C[:-1]]
    for t in set(trans):
        share = trans.count(t) / len(trans)
        if t != 'cut' and share > 0.6 and len(trans) >= 4:
            F.append({'muc': 'canh_bao', 'loai': 'chuyen_canh_lap', 'o': '-', 'cau': f'{share * 100:.0f}% điểm nối dùng "{t}"', 'goi_y': 'trong cùng một ý dùng cắt thẳng; hiệu ứng chỉ ở chỗ đổi ý'})
    fancy = [t for t in trans if t not in ('cut', 'dissolve', 'fade_black')]
    if len(fancy) >= 3: F.append({'muc': 'ghi_chu' if P.get('phong_cach') in ('nang_dong', 'mang_xa_hoi', 'quang_cao') else 'canh_bao', 'loai': 'hieu_ung_loe', 'o': '-', 'cau': f'{len(fancy)} chuyển cảnh trang trí ({", ".join(sorted(set(fancy)))})', 'goi_y': 'phim nghiêm túc: tối đa 1-2 hiệu ứng đặc biệt'})
    cams = [json.dumps(c.get('camera'), sort_keys=True) for c in C if c.get('camera')]
    if len(cams) >= 4 and max(cams.count(x) for x in set(cams)) / len(cams) > 0.7:
        F.append({'muc': 'ghi_chu', 'loai': 'chuyen_dong_lap', 'o': '-', 'cau': 'cùng một chuyển động máy ảo ở hầu hết cảnh', 'goi_y': 'xen cảnh tĩnh và chuyển động khác hướng'})
    txt = [c for c in C if c.get('chu_tren_hinh')]
    if len(C) >= 4 and len(txt) / len(C) > 0.7:
        F.append({'muc': 'canh_bao', 'loai': 'chu_moi_canh', 'o': '-', 'cau': f'{len(txt)}/{len(C)} cảnh có chữ trên hình', 'goi_y': 'chữ chỉ khi có số liệu/tên lời đọc không nói rõ'})
    if C and (C[0].get('nguon') or {}).get('mau'):
        F.append({'muc': 'canh_bao', 'loai': 'mo_dau_yeu', 'o': C[0].get('id'), 'cau': 'mở đầu bằng thẻ màu trơn', 'goi_y': 'khung đầu là hình mạnh nhất, chữ đặt lên hình'})
    voices = {json.dumps(c.get('giong'), ensure_ascii=False) for c in C if c.get('giong')}
    if len(voices) > 1 and not P.get('nhan_vat'):
        F.append({'muc': 'canh_bao', 'loai': 'doi_giong', 'o': '-', 'cau': f'{len(voices)} giọng khác nhau không có nhân vật', 'goi_y': 'một giọng thuyết minh xuyên suốt'})
    for c in C:
        n = c.get('nguon') or {}
        if n.get('tim'): F.append({'muc': 'ghi_chu', 'loai': 'canh_tu_chon', 'o': c.get('id'), 'cau': n['tim'], 'goi_y': 'cảnh tự chọn: xem contact sheet xác nhận đúng nội dung'})
    return M, F


# ---------------------------------------------------------------- client rule ledger
def load_rules(paths, P=None):
    rules = []
    for p in paths or []:
        for r in json.load(open(p, encoding='utf8')):
            if r.get('thay_boi'): continue                      # superseded
            if r.get('het_hieu_luc') and r['het_hieu_luc'] < date.today().isoformat(): continue
            sc = r.get('pham_vi', 'chung')
            if P and sc.startswith('du_an:') and sc.split(':', 1)[1] != P.get('ten'): continue
            if P and sc.startswith('khach:') and sc.split(':', 1)[1] != P.get('khach', ''): continue
            rules.append(r)
    return rules


def rule_findings(P, rules, script_lines):
    F = []; C = P.get('canh', [])
    tgt = {'loi_doc': [(c.get('id'), c.get('thoai') or '') for c in C],
           'chu_tren_hinh': [(c.get('id'), c.get('chu_tren_hinh') or '') for c in C],
           'phu_de': [(c.get('id'), c.get('thoai') or '') for c in C]}
    for r in rules:
        lv = r.get('muc', 'chan'); q = r.get('nguon', '')
        if r['loai'] == 'cam_chu':
            for t in r.get('dich', ['loi_doc', 'chu_tren_hinh', 'phu_de']):
                for w, s in tgt.get(t, []):
                    if re.search(r['mau'], s, flags=re.I):
                        F.append({'muc': lv, 'loai': 'vi_pham_luat', 'o': w, 'cau': s, 'chi_tiet': [r['id'], t], 'goi_y': f'luật {r["id"]}: "{q}"'})
        elif r['loai'] == 'cam_nguon':
            for c in C:
                n = c.get('nguon') or {}
                for k in ('file', 'anh'):
                    if n.get(k) and re.search(r['mau'], n[k], flags=re.I):
                        F.append({'muc': lv, 'loai': 'vi_pham_luat', 'o': c.get('id'), 'cau': os.path.basename(n[k]), 'chi_tiet': [r['id']], 'goi_y': f'luật {r["id"]}: "{q}"'})
        elif r['loai'] == 'giong_vung':
            want = r.get('gia_tri')
            try:
                import voices
                prof = voices.load_profiles()
            except Exception:
                prof = {}
            vs = {c.get('giong') for c in C if isinstance(c.get('giong'), str)} | ({P.get('giong')} if isinstance(P.get('giong'), str) else set())
            for v in vs:
                if v and v != 'auto' and v in prof and prof[v].get('vung') != want:
                    F.append({'muc': lv, 'loai': 'vi_pham_luat', 'o': '-', 'cau': f'giọng {v} là vùng {prof[v].get("vung")}', 'chi_tiet': [r['id']], 'goi_y': f'luật {r["id"]}: "{q}"'})
            if P.get('giong') in (None, 'auto') and P.get('vung') not in (None, want):
                F.append({'muc': lv, 'loai': 'vi_pham_luat', 'o': '-', 'cau': f'vung={P.get("vung")}', 'chi_tiet': [r['id']], 'goi_y': f'luật {r["id"]}: "{q}"'})
        elif r['loai'] == 'toi_da_canh':
            for c in C:
                if float(c.get('thoi_luong') or 0) > float(r['gia_tri']):
                    F.append({'muc': lv, 'loai': 'vi_pham_luat', 'o': c.get('id'), 'cau': f'cảnh {c.get("thoi_luong")}s', 'chi_tiet': [r['id']], 'goi_y': f'luật {r["id"]}: "{q}"'})
    return F


def rules_status(paths, P=None):
    allr = [r for p in paths for r in json.load(open(p, encoding='utf8'))]
    active = load_rules(paths, P)
    checkable = [r for r in active if r['loai'] in ('cam_chu', 'cam_nguon', 'giong_vung', 'toi_da_canh')]
    stale = []
    for r in active:
        if r['loai'] == 'cam_chu':
            try: re.compile(r['mau'])
            except re.error: stale.append((r['id'], 'regex lỗi'))
    return {'tong': len(allr), 'dang_hieu_luc': len(active), 'kiem_tu_dong_duoc': f'{len(checkable)}/{len(active)}',
            'can_nguoi_kiem': [r['id'] for r in active if r not in checkable], 'loi_luat': stale}


# ---------------------------------------------------------------- report
def _strings(x):
    if isinstance(x, str): return [x]
    if isinstance(x, dict): return [t for v in x.values() for t in _strings(v)]
    if isinstance(x, list): return [t for v in x for t in _strings(v)]
    return []


def project_lines(P):
    gfx = [(f"{c.get('id')}:do_hoa", ' . '.join(_strings((c.get('nguon') or {}).get('params'))))
           for c in P.get('canh', []) if (c.get('nguon') or {}).get('params')]
    return gfx + [(c.get('id'), c.get('thoai') or '') for c in P.get('canh', []) if c.get('thoai')] + \
           [(f"{c.get('id')}:chu", c.get('chu_tren_hinh') or '') for c in P.get('canh', []) if c.get('chu_tren_hinh')]


def read_lines(p):
    if p.endswith('.json'):
        d = json.load(open(p, encoding='utf8'))
        if isinstance(d, dict) and 'canh' in d: return project_lines(d), d
        return [(i + 1, x if isinstance(x, str) else (x['text'] if isinstance(x, dict) else x[2])) for i, x in enumerate(d)], None
    return [(i + 1, l.strip()) for i, l in enumerate(open(p, encoding='utf8')) if l.strip()], None


def project_sources(P, root):
    """facts / luat keys of a project -> absolute paths. Rule ledgers normally live OUTSIDE the repo (~/.video_studio/luat/)."""
    def norm(x):
        xs = x if isinstance(x, list) else ([x] if x else [])
        out = [os.path.expanduser(p) for p in xs]
        return [p if os.path.isabs(p) else os.path.join(root, p) for p in out]
    facts = [p for p in norm(P.get('facts')) if os.path.exists(p)]
    rules = [p for p in norm(P.get('luat')) if os.path.exists(p)]
    missing = [p for p in norm(P.get('facts')) + norm(P.get('luat')) if not os.path.exists(p)]
    return facts, rules, missing


def run_project(P, facts=None, rules=None, lang='vi'):
    """Same as run_all for a project dict already in memory."""
    return _finish(P, project_lines(P), load_facts(facts), rules, lang)


def run_all(path, facts=None, rules=None, lang='vi'):
    lines, P = read_lines(path)
    return _finish(P, lines, load_facts(facts), rules, lang)


def _finish(P, lines, ft, rules, lang):
    M, F = script_findings(lines, ft, lang)
    if P:
        M2, F2 = edit_findings(P); M.update(M2); F += F2
        if rules: F += rule_findings(P, load_rules(rules, P), lines)
    order = {'chan': 0, 'canh_bao': 1, 'ghi_chu': 2}
    F.sort(key=lambda f: order[f['muc']])
    verdict = 'CHẶN' if any(f['muc'] == 'chan' for f in F) else ('CẦN XEM' if any(f['muc'] == 'canh_bao' for f in F) else 'ĐẠT')
    return {'ket_luan': verdict, 'chi_so': M, 'phat_hien': F}


def to_md(r, title):
    L = [f'# Kiểm "AI slop" - {title}', '', f'**Kết luận hệ 0 (tất định): {r["ket_luan"]}**', '', '## Chỉ số (tách riêng, không gộp)']
    L += [f'- {k}: {v}' for k, v in r['chi_so'].items()]
    for lv, name in (('chan', 'Phải sửa'), ('canh_bao', 'Cảnh báo'), ('ghi_chu', 'Ghi chú')):
        xs = [f for f in r['phat_hien'] if f['muc'] == lv]
        if xs:
            L += ['', f'## {name} ({len(xs)})']
            L += [f"- [{f['loai']}] {f['o']}: {f['cau']}" + (f" -> {f['chi_tiet']}" if f.get('chi_tiet') else '') + f"\n  - gợi ý: {f['goi_y']}" for f in xs]
    return '\n'.join(L)


def compare(before, after):
    """Independent re-check of a rewrite: accept only if 'chan' went down (or stayed 0), no new finding type appeared
    and no rate metric got worse. Returns (accept, reasons)."""
    cnt = lambda r, lv: sum(f['muc'] == lv for f in r['phat_hien'])
    why, ok = [], True
    for lv in ('chan', 'canh_bao'):
        a, b = cnt(before, lv), cnt(after, lv)
        why.append(f'{lv}: {a} -> {b}')
        if b > a: ok = False
    if cnt(before, 'chan') and cnt(after, 'chan') >= cnt(before, 'chan'): ok = False; why.append('số mục phải sửa không giảm')
    key = lambda f: (f['loai'], f['cau'], json.dumps(f.get('chi_tiet'), ensure_ascii=False))
    fresh = [f for f in after['phat_hien'] if f['muc'] == 'chan' and key(f) not in {key(x) for x in before['phat_hien']}]
    if fresh: ok = False; why.append('bản sửa sinh lỗi chặn mới: ' + '; '.join(f"[{f['loai']}] {f['cau'][:60]}" for f in fresh))
    new = {f['loai'] for f in after['phat_hien']} - {f['loai'] for f in before['phat_hien']}
    if new: ok = False; why.append(f'lỗi mới xuất hiện: {sorted(new)}')
    for k in ('sao_rong_moi_100_chu', 'tu_dem_moi_100_chu'):
        a, b = before['chi_so'].get(k), after['chi_so'].get(k)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and b > a: ok = False; why.append(f'{k} tăng {a} -> {b}')
    return ok, why


def add_rule(path, nguon, loai, mau=None, gia_tri=None, pham_vi='chung', muc='chan', dich=None, nguoi='', thay=None):
    """Store a correction verbatim with provenance; an older rule it replaces is marked superseded, never deleted."""
    R = json.load(open(path, encoding='utf8')) if os.path.exists(path) else []
    rid = f'L{len(R) + 1:03d}'
    r = {'id': rid, 'loai': loai, 'muc': muc, 'pham_vi': pham_vi, 'nguon': nfc(nguon), 'nguoi': nguoi, 'ngay': date.today().isoformat()}
    if mau: re.compile(mau); r['mau'] = mau
    if gia_tri is not None: r['gia_tri'] = gia_tri
    if dich: r['dich'] = dich
    for x in R:
        if thay and x['id'] == thay: x['thay_boi'] = rid
    R.append(r)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    json.dump(R, open(path, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    return rid


REVIEW_BRIEF = """
## Việc của người duyệt (hệ 2 - agent mới, không xem lập luận của người dựng)
Chỉ xét các câu/cảnh bị gắn cờ ở trên. Với mỗi mục:
1. Đồng ý hay không (có thể là báo nhầm - nói rõ vì sao).
2. Nếu đồng ý: viết lại câu (giữ đúng sự thật, không thêm số liệu mới không có nguồn, đọc thành tiếng được, tiếng Việt tự nhiên),
   hoặc đề xuất đổi cảnh/chuyển cảnh cụ thể.
3. Không chấm tổng, không khen. Trả JSON: [{"o": ..., "dong_y": true/false, "ly_do": ..., "viet_lai": ...}]
Sau đó người dựng áp bản viết lại vào project và CHẠY LẠI `slop_guard.py project` (hệ 0). Chỉ nhận bản sửa nếu không chỉ số nào xấu đi
và số mục "Phải sửa" giảm. Người duyệt không tự chứng nhận bản sửa của mình.
"""


def main():
    try: sys.stdout.reconfigure(encoding='utf-8')
    except Exception: pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    for name in ('script', 'project'):
        s = sp.add_parser(name); s.add_argument('path'); s.add_argument('--facts', nargs='*'); s.add_argument('--rules', nargs='*')
        s.add_argument('--lang', default='vi'); s.add_argument('--json')
    r = sp.add_parser('rules'); r.add_argument('paths', nargs='+'); r.add_argument('--project')
    v = sp.add_parser('review'); v.add_argument('path'); v.add_argument('out'); v.add_argument('--facts', nargs='*'); v.add_argument('--rules', nargs='*')
    c = sp.add_parser('compare'); c.add_argument('before'); c.add_argument('after'); c.add_argument('--facts', nargs='*'); c.add_argument('--rules', nargs='*')
    g = sp.add_parser('ghi'); g.add_argument('path'); g.add_argument('--nguon', required=True)
    g.add_argument('--loai', required=True, choices=['cam_chu', 'cam_nguon', 'giong_vung', 'toi_da_canh', 'khac'])
    g.add_argument('--mau'); g.add_argument('--gia-tri'); g.add_argument('--pham-vi', default='chung'); g.add_argument('--muc', default='chan')
    g.add_argument('--dich', nargs='*'); g.add_argument('--nguoi', default=''); g.add_argument('--thay')
    a = ap.parse_args()
    if a.cmd == 'ghi':
        gv = a.gia_tri
        if gv is not None:
            try: gv = float(gv)
            except ValueError: pass
        print(add_rule(a.path, a.nguon, a.loai, a.mau, gv, a.pham_vi, a.muc, a.dich, a.nguoi, a.thay)); return
    if a.cmd == 'compare':
        load = lambda x: json.load(open(x, encoding='utf8')) if x.endswith('slop.json') else run_all(x, a.facts, a.rules)
        ok, why = compare(load(a.before), load(a.after))
        print('NHẬN' if ok else 'KHÔNG NHẬN', '|', '; '.join(why)); sys.exit(0 if ok else 3)
    if a.cmd == 'rules':
        P = json.load(open(a.project, encoding='utf8')) if a.project else None
        print(json.dumps(rules_status(a.paths, P), ensure_ascii=False, indent=1)); return
    if a.cmd == 'review':
        res = run_all(a.path, a.facts, a.rules); os.makedirs(a.out, exist_ok=True)
        p = os.path.join(a.out, 'SLOP_REVIEW.md'); open(p, 'w', encoding='utf8').write(to_md(res, os.path.basename(a.path)) + '\n' + REVIEW_BRIEF)
        json.dump(res, open(os.path.join(a.out, 'slop.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=1)
        print(res['ket_luan'], '->', p); return
    res = run_all(a.path, a.facts, a.rules, a.lang)
    print(to_md(res, os.path.basename(a.path)))
    if a.json: json.dump(res, open(a.json, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    sys.exit(2 if res['ket_luan'] == 'CHẶN' else 0)


if __name__ == '__main__':
    main()
