---
name: video-studio
description: Tự động TẠO và CHỈNH SỬA video chuyên nghiệp bằng một lệnh - dựng phim mới từ storyboard (cắt nguồn đúng ranh giới shot, ảnh Ken Burns mượt, chữ trên hình, hoà cảnh, giọng đọc TTS tiếng Việt giọng Bắc, nhạc nền ducking, LUFS chuẩn, phụ đề), thay giọng thuyết minh của video có sẵn (tách nhạc, tự dò mốc câu, đọc lại, giữ nhạc gốc), phụ đề tự động, sửa nhịp khung hình giật (60p/30p→24p), QC tự động (khung lạc, chớp, đứng hình, độ giật, LUFS, độ khớp lời) và đẩy bản nháp sang CapCut. Dùng khi người dùng muốn làm video, dựng/cắt/ghép video, lồng tiếng/thuyết minh lại, đổi giọng đọc, thêm phụ đề, sửa video giật/mờ/lệch tiếng, kiểm tra video trước khi giao, làm phim doanh nghiệp/giới thiệu dự án, hoặc dựng phim ngắn/micro-drama bằng AI.
---

# Video Studio - dựng phim tự động

Skill này **tự làm ra video thành phẩm**, không chỉ hướng dẫn. Mọi việc đi qua một cửa: `scripts/autovideo.py`.
Phần kiến thức nghề (góc máy, nhịp, âm thanh, phụ đề, CapCut, phim AI, bài học thực tế) nằm ở `references/` để
quyết định đúng khi lập storyboard và khi đọc báo cáo QC.

Đường dẫn script: thư mục chứa file này + `/scripts/` (cài theo README: `~/.claude/skills/video-studio/scripts`).

## 0. Lệnh slash cho người dùng

`/video:plan` bàn ý tưởng - kịch bản - phân cảnh - ánh sáng · `/video:make` dựng phim mới · `/video:revoice` lồng tiếng lại ·
`/video:subs` phụ đề · `/video:reframe` đổi khung dọc/vuông · `/video:library` kho cảnh · `/video:qc` kiểm tra ·
`/video:voices` nghe thử giọng · `/video:fix` sửa giật/fps/rung · `/video:capcut` đẩy sang CapCut.
Người dùng nói tự nhiên (không gõ lệnh) thì vẫn làm theo bảng dưới.

## 1. Chọn lệnh theo yêu cầu

| Người dùng muốn | Làm |
|---|---|
| Làm video mới từ ý tưởng/kịch bản + kho nguồn (video, ảnh) | Viết `project.json` theo `templates/project_make.json` → `autovideo.py make project.json --out TEN_v1.mp4` |
| Đổi giọng thuyết minh / lồng tiếng lại video có sẵn | `autovideo.py revoice VIDEO.mp4 --script loi.txt --voice "Thiện Minh" --out TEN_v1.mp4 [--subs]` |
| Thêm phụ đề cho video | `autovideo.py subs VIDEO.mp4 --script loi.txt --out TEN_sub.mp4` (tự dò mốc trên tiếng) |
| Kiểm video trước khi giao | `autovideo.py qc VIDEO.mp4` (+ `contact_sheet.py` để soát mắt) |
| Đổi fps bất kỳ 24/25/30/50/60/120, slow-mo, sửa giật nhịp | `fps_convert.py convert SRC OUT --fps 24 [--slowmo 4]` (RIFE GPU) |
| Video ngang → dọc/vuông bám chủ thể; pan/zoom ảo; chống rung | `camera.py reframe / move / stabilize` |
| Chọn cảnh đẹp nhất trong kho footage, tìm theo mô tả | `shot_select.py scan / best / search` |
| Khớp màu giữa cảnh, look điện ảnh | `grade.py match / look / apply` |
| Xuất theo nền tảng, dò nhịp nhạc | `deliver.py export <preset> / beats` |
| Bàn ý tưởng, phân cảnh, ánh sáng, góc máy trước khi dựng | `/video:plan` + `references/11-dien-anh-cao-cap.md` |
| Chọn giọng đọc | `tts_vi.py --list`, sinh mẫu nhiều giọng, `speech_check.py` đo, gửi người dùng nghe |
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
- Giọng mặc định: nam miền Bắc **Thiện Minh** (khuyên dùng cho phim trang trọng). Phong cách tin tức: Minh Đức. Danh sách: `05-am-thanh-giong-doc.md`.

## 3. Luật bất biến

1. **Không xoá/ghi đè bản giao.** Bản mới `_vN`. Thay bản chính chỉ khi người dùng duyệt: `mv -n` bản cũ thành `_luu_<mo_ta>`, `cp -n` bản mới, `cmp` xác nhận.
2. **Đo trước khi nói** - dùng số trong `BAO_CAO_QC.md`; chưa đo thì nói chưa đo.
3. **Nội dung đúng sự thật**: đúng công trình/đơn vị, không stock nước ngoài, QR, quảng cáo, khẩu hiệu lạ, người không được phép xuất hiện.
4. **Bản dịch đúng 100 % nghĩa và ngữ cảnh**; câu phân vân thì hỏi.
5. **Không nhập mật khẩu/khoá API** thay người dùng.
6. Tải mô hình chỉ từ nguồn gốc, ưu tiên `.safetensors`, cài venv riêng.
7. Giao tiếp tiếng Việt.

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
| Ánh sáng, ống kính, góc máy, chuyển động, màu, âm thanh, dựng cao cấp | `references/11-dien-anh-cao-cap.md` |

## 5. Bộ script

| Script | Vai trò |
|---|---|
| `autovideo.py` | **Cửa chính**: `make`, `revoice`, `subs`, `qc` |
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
