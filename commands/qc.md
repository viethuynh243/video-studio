---
description: Kiểm tra video trước khi giao - giật, khung lạc, chớp, đứng hình, âm lượng, lời, phụ đề, nội dung
argument-hint: <video> [kịch bản để so lời] [nền tảng: youtube/facebook/trình chiếu/phát sóng]
---

Dùng skill **video-studio** để QC. Yêu cầu: $ARGUMENTS

1. Chạy `python scripts/autovideo.py qc <video>`. Chạy thêm `contact_sheet.py <video> <video>_qc/sheet.jpg` rồi xem ảnh.
2. Có kịch bản → tách giọng (`demucs_split.py`), chạy `speech_check.py` trên rãnh giọng để đo % lời khớp.
3. So với ngưỡng ở `references/08`. Âm lượng theo nền tảng ở `references/05` mục 6.
4. Trả lời bằng bảng **Đạt / Chưa đạt** cho từng hạng mục, kèm số đo và mốc thời gian lỗi. Mỗi lỗi đề xuất cách sửa và lệnh `/video:*` tương ứng.
   Không sửa file gốc.
