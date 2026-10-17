---
description: Sửa video bị giật/khựng nhịp, rung, sai fps (24/25/30/50/60/120), lọt khung lạc, chớp đen, mờ, lệch tiếng, âm lượng
argument-hint: <video> [mô tả lỗi, mốc thời gian nếu biết] [fps đích]
---

Dùng skill **video-studio** để sửa lỗi. Yêu cầu: $ARGUMENTS

1. Chẩn đoán:
   - `autovideo.py qc <video>`, `fps_convert.py probe <video>` (fps thật, VFR, khung đệm), `contact_sheet.py`;
   - đọc `references/03` (hình) hoặc `references/05` (tiếng).
2. Sửa theo loại lỗi:

| Lỗi | Lệnh |
|---|---|
| Đổi fps 60/30 → 24/25 bị giật 2:3 | `fps_convert.py convert <src> <out> --fps 24` (RIFE lấy mẫu đều; từ ≥ 2× sẽ có motion blur 180°) |
| Cần 60/120 fps | `--fps 60` hoặc `--fps 120` (nội suy RIFE) |
| Slow motion | `--slowmo 2..5` (nguồn 120p là slow-mo thật) |
| 24p bị đệm thành 30p | `probe` tự phát hiện, `convert` tự bỏ khung đệm |
| 25 ↔ 24 | conform (đổi tốc độ 4 %, nhớ đổi tiếng theo) |
| Rung tay | `camera.py stabilize` (`--tripod` để khoá hẳn) |
| Khung lạc, chớp đen | cắt lùi 2-3 khung vào trong shot |
| Đứng hình | thay bằng đoạn nguồn dài hơn |
| Lệch tiếng | đo độ lệch rồi dùng `-itsoffset` |
| Âm lượng | `deliver.py export ... <preset>` |
| Màu lệch giữa các cảnh | `grade.py match` + `apply` |

3. Xuất bản mới `<ten>_fix_v1.mp4` (không ghi đè), rồi chạy QC lại.
4. Báo số đo trước/sau: judder, cadence, fps, LUFS.
