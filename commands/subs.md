---
description: Tạo phụ đề tự động (SRT + burn-in), căn đúng theo tiếng, tuỳ chọn dịch sang ngôn ngữ khác
argument-hint: <video> [lời: .txt/.json; trống = tự nghe] [dịch sang: en/lo/...]
---

Dùng skill **video-studio** để làm phụ đề. Yêu cầu: $ARGUMENTS

1. Có lời → dùng lời đó. Không có → tự nghe bằng Whisper trên giọng đã tách (`demucs_split.py`), sửa chính tả,
   viết thành `.txt` mỗi câu một dòng.
2. Cần dịch → dịch đúng 100 % nghĩa và ngữ cảnh theo `references/06`, không dùng "—". Ghi lại các câu còn phân vân để hỏi.
3. Chạy `python scripts/autovideo.py subs <video> --script <loi.txt> --out <ten>_sub.mp4`.
   File `.srt` được tạo cạnh file đầu ra.
4. Soát: mỗi phụ đề tối đa 2 dòng, mỗi dòng ≤ 42 ký tự, không che chữ có sẵn trên hình (xem `contact_sheet.py` tại các mốc có chữ).
5. Gửi video cùng file `.srt`.
