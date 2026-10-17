---
description: Chuyển video ngang sang dọc 9:16 / vuông / 4:5 thông minh - khung tự bám người nói và chủ thể như người quay thật
argument-hint: <video> [9:16 | 1:1 | 4:5] [preset: tiktok/reels/square/feed_4x5]
---

Dùng skill **video-studio** để đổi khung. Yêu cầu: $ARGUMENTS

1. Kiểm nguồn bằng `fps_convert.py probe`. Nguồn 1080p mà xuất dọc thì báo trước: hình sẽ phóng ~1,8×, nét giảm. Nguồn 4K thì giữ nét.
2. Chạy `python scripts/camera.py reframe <video> <ten>_doc.mp4 --aspect 9:16 --size 1080x1920`.
   Phương pháp:
   - mặt người (YuNet) là ưu tiên;
   - cộng độ nổi bật và chuyển động;
   - shot đứng yên thì khoá khung như tripod; shot có chuyển động thì pan mượt có giới hạn tốc độ;
   - không pan qua điểm cắt.
3. Ghép lại tiếng: `deliver.py export <video> tiktok <ten>_tiktok.mp4 --reframe` làm trọn gói: khung dọc, 30 fps, -14 LUFS.
4. Soát `contact_sheet.py`: chủ thể có bị cắt mặt/tay không, chữ có nằm trong vùng an toàn không (tránh 15 % trên, 20 % dưới).
   Chỗ nào sai thì cắt đoạn đó, chạy lại với `--mode static` hoặc `--mode follow`.
