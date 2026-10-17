---
description: Chọn giọng đọc theo mục đích video - gợi ý có căn cứ, nghe thử bằng chính lời của bạn, giọng riêng hoặc nhân bản giọng
argument-hint: [mục đích: doanh nghiệp / thời sự / tài liệu / quảng cáo / mạng xã hội / hướng dẫn / sang trọng / trẻ em / sự kiện] [nam/nữ] [Bắc/Trung/Nam] [lời mẫu]
---

Dùng skill **video-studio** để chọn giọng. Yêu cầu: $ARGUMENTS

1. Chưa có hồ sơ giọng (`~/.cache/video_studio/voices.json`) → chạy `python scripts/voices.py profile` một lần (đo độ đọc đúng, cao độ, tốc độ của mọi giọng).
2. `python scripts/voices.py suggest --muc-dich <md> [--gioi-tinh nam|nu] [--vung bac|trung|nam] [--tram tram|vua|sang] --top 4`.
   Không ép một giọng: luôn đưa 3-4 lựa chọn khác nhau (vd. 1 trầm, 1 sáng, 1 khác giới) kèm lý do.
3. Sinh mẫu bằng lời thật của người dùng (hoặc 2 câu đầu kịch bản), qua `accuracy.guarded_synth` (tự đọc lại câu sai), xuất mp3
   `1_<Ten>_<phongcach>.mp3`, gửi nghe (SendUserFile) + bảng: giọng, phong cách, % đọc đúng, cao độ, tốc độ.
4. Muốn giọng riêng: ghi âm 5-10 s sạch (người nói đồng ý) → `clone:<file.wav>`; hoặc ghi âm cả câu → `ghi_am` trong cảnh.
5. Ghi lựa chọn vào project (`giong`, hoặc `giong` theo từng cảnh/nhân vật). Từ khó đọc → thêm vào `phat_am`.
