---
description: Lồng tiếng / thay giọng thuyết minh cho video có sẵn, giữ nhạc gốc, tự căn mốc từng câu
argument-hint: <video> [lời mới: file .txt hoặc gõ thẳng] [giọng, ví dụ "Minh Đức"] [có phụ đề?]
---

Dùng skill **video-studio** để thay giọng thuyết minh. Yêu cầu: $ARGUMENTS

1. Xác định video nguồn và lời đọc:
   - Người dùng không đưa lời mới → lấy lời cũ bằng Whisper trên giọng đã tách, sửa chính tả, cho người dùng xem nhanh rồi dùng.
   - Có lời mới → ghi ra file `.txt`, mỗi dòng một câu.
2. Giọng: theo yêu cầu người dùng; nếu chưa nói thì `--voice auto --muc-dich <mục đích>` (+ `--gioi-tinh`, `--vung`) và báo giọng đã chọn kèm lý do. Có thể dùng `clone:<mẫu.wav>` (người nói đồng ý) hoặc Edge. Từ viết tắt khó đọc: thêm `--phat-am tu_dien.json`.
3. Chạy `python scripts/autovideo.py revoice <video> --script <loi.txt> --voice <giọng|auto> [--muc-dich ...] --out <ten>_v1.mp4`.
   Thêm `--subs` nếu cần phụ đề cứng, `--capcut <ten>` nếu muốn bản nháp CapCut.
4. Đọc `BAO_CAO_QC.md`. Lời khớp < 97 % → nghe đoạn sai, sửa chữ (viết lại số/từ khó), chạy lại thành bản `_v2`.
5. Gửi bản mới kèm báo cáo: giọng, % lời khớp, LUFS, các câu phải tăng tốc (nếu có).
   Không thay bản chính khi người dùng chưa duyệt.
