---
name: video-studio
description: Tự động TẠO và CHỈNH SỬA video chuyên nghiệp bằng một lệnh - dựng phim mới từ storyboard (cắt nguồn đúng ranh giới shot, ảnh Ken Burns mượt, chữ trên hình, hoà cảnh, giọng đọc TTS tiếng Việt giọng Bắc, nhạc nền ducking, LUFS chuẩn, phụ đề), thay giọng thuyết minh của video có sẵn (tách nhạc, tự dò mốc câu, đọc lại, giữ nhạc gốc), phụ đề tự động, sửa nhịp khung hình giật (60p/30p→24p), QC tự động (khung lạc, chớp, đứng hình, độ giật, LUFS, độ khớp lời), soi và sửa "AI slop" (câu sáo rỗng, số liệu không nguồn, khẳng định suông, dựng đều như máy, luật riêng của khách) và đẩy bản nháp sang CapCut. Dùng khi người dùng muốn làm video, dựng/cắt/ghép video, lồng tiếng/thuyết minh lại, đổi giọng đọc, thêm phụ đề, sửa video giật/mờ/lệch tiếng, kiểm tra video trước khi giao, kiểm kịch bản/phim nghe như AI viết, làm phim doanh nghiệp/giới thiệu dự án, hoặc dựng phim ngắn/micro-drama bằng AI.
---

# Video Studio - dựng phim tự động

Skill này **tự làm ra video thành phẩm**, không chỉ hướng dẫn. Mọi việc đi qua một cửa: `scripts/autovideo.py`.
Phần kiến thức nghề (góc máy, nhịp, âm thanh, phụ đề, CapCut, phim AI, bài học thực tế) nằm ở `references/` để
quyết định đúng khi lập storyboard và khi đọc báo cáo QC.

Đường dẫn script: thư mục chứa file này + `/scripts/` (cài theo README: `~/.claude/skills/video-studio/scripts`).

## 0. Lệnh slash cho người dùng

`/video:plan` bàn ý tưởng - kịch bản - phân cảnh - ánh sáng · `/video:make` dựng phim mới · `/video:revoice` lồng tiếng lại ·
`/video:subs` phụ đề · `/video:reframe` đổi khung dọc/vuông · `/video:library` kho cảnh · `/video:qc` kiểm tra ·
`/video:voices` chọn giọng theo mục đích · `/video:fix` sửa giật/fps/rung · `/video:critic` phê bình độc lập · `/video:slop` soi và sửa "AI slop" · `/video:capcut` đẩy sang CapCut.
Người dùng nói tự nhiên (không gõ lệnh) thì vẫn làm theo bảng dưới.

## 0b. Công cụ MCP `video-studio` (ưu tiên khi có)

Khi các tool `mcp__video-studio__*` có trong phiên, gọi thẳng chúng thay vì chạy script bằng Bash:
- **Nhanh**: `video_probe`, `video_qc`, `contact_sheet`, `voices_suggest`, `voices_catalogue`, `pronunciation_preview`, `shot_search`, `motion_stills`,
  `slop_check`, `slop_compare`.
- **Việc dài** (trả `job_id`, theo dõi bằng `job_status` / `job_list`): `make_video`, `revoice_video`, `subtitle_video`, `convert_fps`,
  `reframe_video`, `stabilize_video`, `motion_graphic`, `critic_kit`, `voice_samples`.
Đăng ký một lần: `claude mcp add --scope user video-studio -e PYTHONIOENCODING=utf-8 -- python <repo>/scripts/mcp_server.py`.

## 1. Chọn lệnh theo yêu cầu

| Người dùng muốn | Làm |
|---|---|
| Làm video mới từ ý tưởng/kịch bản + kho nguồn (video, ảnh) | Viết `project.json` theo `templates/project_make.json` → `autovideo.py make project.json --out TEN_v1.mp4` |
| Đổi giọng thuyết minh / lồng tiếng lại video có sẵn | `autovideo.py revoice VIDEO.mp4 --script loi.txt [--voice auto --muc-dich thoi_su] --out TEN_v1.mp4 [--subs]` |
| Thêm phụ đề cho video | `autovideo.py subs VIDEO.mp4 --script loi.txt --out TEN_sub.mp4` (tự dò mốc trên tiếng) |
| Kiểm video trước khi giao | `autovideo.py qc VIDEO.mp4` (+ `contact_sheet.py` để soát mắt) |
| Đổi fps bất kỳ 24/25/30/50/60/120, slow-mo, sửa giật nhịp | `fps_convert.py convert SRC OUT --fps 24 [--slowmo 4]` (RIFE GPU) |
| Video ngang → dọc/vuông bám chủ thể; pan/zoom ảo; chống rung | `camera.py reframe / move / stabilize` |
| Chọn cảnh đẹp nhất trong kho footage, tìm theo mô tả | `shot_select.py scan / best / search` |
| Khớp màu giữa cảnh, look điện ảnh | `grade.py match / look / apply` |
| Xuất theo nền tảng, dò nhịp nhạc | `deliver.py export <preset> / beats` |
| Bàn ý tưởng, phân cảnh, ánh sáng, góc máy trước khi dựng | `/video:plan` + `references/11-dien-anh-cao-cap.md` |
| Bản đồ tuyến động, thẻ chương, đồ hoạ số liệu (motion graphics bằng code) | `motion_html.py stills/render` + `templates/motion/*.html`, hoặc cảnh `"nguon": {"html": ...}` |
| Kịch bản/phim nghe "giọng AI": sáo rỗng, số không nguồn, khẳng định suông, nhịp đều, hiệu ứng tràn lan | `/video:slop` (`slop_guard.py` đo → agent mới đề xuất sửa → `compare` đo lại) |
| Chấm phim trước khi gửi (người chấm khác người dựng) | `/video:critic` (`critic.py` + agent mới, chấm đến khi mọi hạng mục ≥ 8) |
| Chọn giọng đọc theo mục đích | `voices.py suggest --muc-dich thoi_su --gioi-tinh nu`, sinh mẫu 2-3 giọng gợi ý, gửi người dùng nghe |
| Đưa sang CapCut để tinh chỉnh tay | thêm `--capcut TEN_NHAP` vào `make`/`revoice`, hoặc `capcut_api.py build --spec` |
| Phim AI/micro-drama | `references/09-phim-ai-pipeline.md` + `storyboard.py jobs` |

Mọi lệnh tự: không ghi đè file đã có, lưu file trung gian ở `<out>_work/`, ghi `BAO_CAO_QC.md` (lỗi hình, độ giật,
LUFS, % lời khớp kịch bản). **Đọc báo cáo trước khi gửi** và nêu số đo trong câu trả lời.

## 2. Lập project.json cho `make` (quan trọng nhất)

- Mỗi `canh` một ý lời. `nguon` là một trong: `{"file", "vao", "ra"}` (video), `{"anh", "hieu_ung": zoom_in|zoom_out|pan_left|pan_right}`, `{"mau": "#0E2440"}`.
- Thời lượng cảnh tự tính = max(`thoi_luong`, độ dài giọng + 0,9 s). Cảnh video tự lùi vào **trong một shot gốc**; nguồn không đủ sạch thì tự rút cảnh, không freeze.
- Hình phải **đúng thứ lời đang nói** (đúng công trình, đúng sự kiện) - chọn nguồn bằng `probe_qc.py --inventory` + `contact_sheet.py` trên nguồn, đừng đoán theo tên file.
- `chuyen_canh`: `cut` trong cùng ý, `dissolve` khi đổi ý/không gian. Cảnh ≤ 7-8 s.
- Lời viết như nói; số và đơn vị để nguyên (`119 km`, `100 km/h`) - `tts_vi.py` tự chuẩn hoá (gạch nối/gạch ngang không bị đọc thành "đến").
- `chu_tren_hinh`: ngắn, chỉ số liệu/tên có trong lời; không dùng "—".
- Nâng cao: `fps` dự án bất kỳ (nguồn khác fps tự qua `fps_convert`), cảnh video có `slowmo`, `camera` (push/pan ảo), `on_dinh`,
  `khung_thong_minh` (tự bám chủ thể khi xuất dọc); dự án có `mau` (khớp màu + look) và `cat_theo_nhac` (cắt trên phách).
- **Giọng không bị ép**: `"giong": "auto"` (mặc định) chọn theo `"muc_dich"` (`doanh_nghiep`, `thoi_su`, `tai_lieu`, `quang_cao`,
  `mang_xa_hoi`, `huong_dan`, `sang_trong`, `tre_em`, `su_kien`) + `"gioi_tinh"`, `"vung"`, `"am_sac"` (tram/vua/sang), dựa trên hồ sơ đo
  của từng giọng (`voices.py profile`: độ đọc đúng, cao độ, tốc độ). Hoặc chỉ định: tên giọng VieNeu, `{"edge": "vi-VN-HoaiMyNeural"}`,
  `{"clone": "mau_giong.wav"}` (người nói phải đồng ý), hoặc ghi âm thật `"ghi_am": "cau3.wav"` cho từng cảnh. Mỗi cảnh/nhân vật có thể có giọng riêng.
  Luôn đưa 2-3 giọng gợi ý (`voices.py suggest`) cho người dùng nghe trước khi chốt.
- **Chính xác**: từ điển phát âm `templates/phat_am.json` + `"phat_am"` riêng dự án (viết tắt, tên riêng); mỗi câu được Whisper nghe lại,
  câu < `"do_chinh_xac"` (0,97) tự đọc lại tối đa `"doc_lai"` lần, báo cáo từng câu; phụ đề căn theo **từng từ** thật.
- **Tuỳ chọn dựng**: `"phong_cach"`: `trang_trong` | `dien_anh` (letterbox 2.39, filmic) | `tai_lieu` | `nang_dong` (cắt theo phách) | `mang_xa_hoi`
  (khung bám chủ thể). Chuyển cảnh từng cảnh: `cut`, `dissolve`, `fade_black`, `dip_white`, `wipe_left/right`, `slide_left/right`, `zoom_in`.
  Khung: `"khung"`: `fill` (cắt đầy) | `fit_blur` (giữ trọn hình, nền mờ) | `smart` (bám chủ thể). `"letterbox": 2.39`. Mọi tuỳ chọn ghi đè được ở từng cảnh.
- **Đồ hoạ động**: `"nguon": {"html": "templates/motion/route_map.html", "params": {...}}` (bản đồ tuyến vẽ dần, thẻ chương...). `make` tự xuất thêm bản **chỉ có nhạc** `_chi_nhac.mp4`. Brief đạo diễn + `facts.md` trước khi dựng phim lớn (`references/12`).
- **Chống AI slop**: `"facts": "facts.md"` (mỗi số + câu gốc + tài liệu + ngày) và `"luat": ["~/.video_studio/luat/<khach>.json"]`
  (sổ luật khách, để ngoài repo). `make` tự kiểm và ghi mục "Chống AI slop" vào báo cáo; `"chan_khi_slop": true` để dừng khi còn số bịa/vi phạm luật.
  Khách sửa tay câu nào thì chép nguyên văn vào sổ luật (`slop_guard.py ghi`) để phim sau tự bắt (`references/13`).
- **Tự chọn cảnh**: `"kho_canh": "kho.json"` (từ `shot_select.py scan --clip`) và `"nguon": {"tim": "aerial view of a highway at sunset"}`
  → lấy cảnh khớp nhất, đủ dài, chưa dùng, điểm chất lượng cao. Viết mô tả tìm bằng tiếng Anh.

## 3. Luật bất biến

1. **Không xoá/ghi đè bản giao.** Bản mới `_vN`. Thay bản chính chỉ khi người dùng duyệt: `mv -n` bản cũ thành `_luu_<mo_ta>`, `cp -n` bản mới, `cmp` xác nhận.
2. **Đo trước khi nói** - dùng số trong `BAO_CAO_QC.md`; chưa đo thì nói chưa đo.
3. **Nội dung đúng sự thật**: đúng công trình/đơn vị, không stock nước ngoài, QR, quảng cáo, khẩu hiệu lạ, người không được phép xuất hiện.
4. **Bản dịch đúng 100 % nghĩa và ngữ cảnh**; câu phân vân thì hỏi.
5. **Không nhập mật khẩu/khoá API** thay người dùng.
6. Tải mô hình chỉ từ nguồn gốc, ưu tiên `.safetensors`, cài venv riêng.
7. Giao tiếp tiếng Việt.
8. **Không giao số bịa**: mọi số trên hình/lời đọc phải có trong `facts` hoặc khai `[tính: ...]`. Bản sửa do agent viết chỉ được nhận sau khi
   `slop_guard.py compare` đo lại (người viết không tự xác nhận).

## 4. Nạp tham chiếu khi cần

| Khi nào | File |
|---|---|
| Quy trình, phiên bản, báo cáo gửi khách | `references/01-quy-trinh.md` |
| Góc máy, cỡ cảnh, nhịp cắt, chuyển cảnh, ảnh tĩnh | `references/02-ngon-ngu-hinh-anh.md` |
| Giật, khựng, khung lạc, đổi fps | `references/03-khung-hinh-chuyen-dong.md` |
| Màu, scale/crop, logo, xuất file | `references/04-hinh-anh-mau-xuat.md` |
| Giọng đọc, TTS, nhạc, LUFS | `references/05-am-thanh-giong-doc.md` |
| Phụ đề, dịch, chữ trên hình | `references/06-phu-de-dich-chu.md` |
| CapCut (MCP, VectCutAPI, web) | `references/07-capcut.md` |
| QC trước khi gửi | `references/08-qc-giao-file.md` |
| Phim AI / micro-drama | `references/09-phim-ai-pipeline.md` |
| Bài học đã trả giá | `references/10-bai-hoc-thuc-te.md` |
| Ánh sáng, ống kính, khẩu/màn trập/ISO/ND theo tình huống, prompt video AI, góc máy, màu, âm thanh, dựng | `references/11-dien-anh-cao-cap.md` |
| Chống "AI slop": số có gốc, sổ luật khách, người duyệt mù, đo lại trước khi nhận | `references/13-chong-ai-slop.md` |
| Brief đạo diễn, luật chống "chuyển động kiểu AI", đồ hoạ bằng code, vòng phê bình, dự án lớn (GES, 3D, hiện trạng) | `references/12-dao-dien-motion-va-phe-binh.md` |

## 5. Bộ script

| Script | Vai trò |
|---|---|
| `autovideo.py` | **Cửa chính**: `make`, `revoice`, `subs`, `qc` |
| `voices.py` | Hồ sơ đo từng giọng, gợi ý giọng theo mục đích, nhiều nguồn giọng (VieNeu, Edge, nhân bản, ghi âm) |
| `accuracy.py` | Từ điển phát âm, nghe lại từng câu, tự đọc lại câu sai |
| `motion_html.py` | Đồ hoạ động bằng HTML + `seek(t)` (Playwright), motion blur sub-frame tự động |
| `critic.py` | Bộ tư liệu chấm độc lập: contact/phone/strip, khung chết, chữ đủ lâu, kiểm slop (cùng `slop_guard`) |
| `slop_guard.py` | Chống AI slop tất định: số có nguồn/suy ra, sáo rỗng, khẳng định suông, nhịp, dựng đều, sổ luật khách; `compare` nhận/không nhận bản sửa |
| `mcp_server.py` | MCP server: 21 công cụ (nhanh + hàng đợi job) để Claude gọi trực tiếp |
| `probe_qc.py` | Kiểm kê nguồn / QC phim (khung lạc, chớp, khung lặp, đứng hình, giật, cadence, LUFS, viền đen) |
| `contact_sheet.py` | Tờ liên hoàn 3 khung/shot để soát mắt |
| `fps_convert.py` | Bộ chuyển fps 24-120, slow-mo, motion blur 180°, phát hiện khung đệm (RIFE/flow) |
| `camera.py` | Reframe thông minh (mặt người + độ nổi bật), pan/zoom ảo, chống rung vidstab |
| `shot_select.py` | Kho cảnh: tách shot, chấm điểm, tìm theo mô tả (CLIP) |
| `grade.py` | LUT khớp màu, cân tự động, look; áp LUT |
| `deliver.py` | Preset xuất nền tảng, dò phách nhạc |
| `cadence_fix.py` | Sửa nhịp từng đoạn bằng optical flow (bản cũ, không cần GPU) |
| `tts_vi.py` | VieNeu-TTS tiếng Việt (25 giọng), chuẩn hoá chữ, tự chạy trong venv riêng |
| `speech_check.py` | % lời khớp kịch bản (Whisper), ước lượng phương ngữ |
| `voice_mix.py` | Đặt câu theo mốc, chuỗi xử lý giọng, ducking, LUFS, ghép video |
| `subs.py` | Chia câu phụ đề, SRT/ASS, burn-in |
| `demucs_split.py` | Tách giọng/nhạc |
| `capcut_api.py` | Tạo nháp CapCut desktop qua VectCutAPI |
| `storyboard.py` | Kiểm storyboard, shotlist, hàng đợi job phim AI |

Môi trường (cài bằng `install.ps1`): ffmpeg trong PATH; Python 3.12 (numpy, opencv, soundfile, librosa, Pillow, faster-whisper, torch, demucs);
VieNeu ở `~/tools/venv_vieneu` (đổi bằng `VIENEU_PY`); RIFE ở `~/tools/rife/` (`RIFE_BIN`); YuNet ở `~/tools/models/` (`YUNET_ONNX`); VectCutAPI ở `~/tools/VectCutAPI` (cổng 9001).
