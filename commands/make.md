---
description: Dựng phim mới hoàn chỉnh từ kịch bản + thư mục nguồn (video, ảnh) - giọng đọc, nhạc, phụ đề, QC
argument-hint: <kịch bản hoặc project.json> [thư mục nguồn] [thời lượng, giọng, tỉ lệ khung...]
---

Dùng skill **video-studio** để dựng một video hoàn chỉnh. Yêu cầu: $ARGUMENTS

1. Nếu đã có `project.json` → kiểm bằng `scripts/storyboard.py check` rồi dựng luôn.
   Nếu chỉ có kịch bản/ý tưởng + thư mục nguồn:
   - kiểm kê nguồn (`probe_qc.py --inventory`, `contact_sheet.py`) để biết mỗi file quay gì;
   - chia lời thành cảnh, chọn đúng hình cho từng ý theo `references/02`;
   - viết `project.json` theo `templates/project_make.json` (`giong: auto` + `muc_dich` theo mục đích video, hoặc giọng người dùng chọn; `phong_cach`, `khung`, chuyển cảnh theo yêu cầu; 1920×1080, 25 fps nếu không nói khác).
2. Chạy `python scripts/autovideo.py make project.json --out <TEN>_v1.mp4` (tên mới, không ghi đè).
3. Đọc `<out>_work/BAO_CAO_QC.md`, rồi soát `contact_sheet.py` của bản dựng. Còn lỗi hình, cảnh sai nội dung hoặc lời khớp < 97 % thì sửa project và dựng lại `_v2`.
4. Gửi file cho người dùng (SendUserFile), kèm báo cáo ngắn bằng tiếng Việt: thời lượng, số cảnh, số đo QC, các cảnh báo về nguồn, việc cần người dùng quyết.

Chỉ hỏi lại khi thiếu thứ không tự quyết được (ví dụ không có nguồn hình nào cho một ý của lời).
