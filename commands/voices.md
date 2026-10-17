---
description: Nghe thử các giọng đọc tiếng Việt (Bắc/Trung/Nam, nam/nữ) bằng chính lời của bạn rồi chọn giọng
argument-hint: [đoạn lời mẫu hoặc file] [lọc: nam bắc / nữ / tin tức ...]
---

Dùng skill **video-studio** để chọn giọng đọc. Yêu cầu: $ARGUMENTS

1. Liệt kê giọng: `python scripts/tts_vi.py --list`. Lọc theo yêu cầu; mặc định là các giọng nam miền Bắc.
2. Lấy đoạn lời mẫu (người dùng đưa, hoặc 2 câu đầu kịch bản đang làm). Sinh bằng các giọng đã lọc:
   `python scripts/tts_vi.py <loi.json> <thu_muc> --voices "Thiện Minh" "Minh Đức" ...`
3. Đo `speech_check.py <file>_all.wav --ref <loi.json>` cho từng giọng; loại giọng đọc sai thanh (< 97 %).
4. Xuất mp3, đặt tên `1_Nam_Bac_<Ten>_<phongcach>.mp3`, gửi người dùng nghe (SendUserFile). Kèm bảng: giọng, phong cách, % lời khớp, nhận xét.
5. Lưu lại mọi mẫu. Ghi giọng người dùng chọn làm `giong_mac_dinh` cho dự án.
