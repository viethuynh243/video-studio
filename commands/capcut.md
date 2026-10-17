---
description: Đẩy video/giọng/nhạc/phụ đề thành bản nháp CapCut desktop để chỉnh tay (qua VectCutAPI)
argument-hint: <video hoặc thư mục _work> [tên bản nháp]
---

Dùng skill **video-studio** để tạo bản nháp CapCut. Yêu cầu: $ARGUMENTS

1. Kiểm server: `python scripts/capcut_api.py status`. Nếu server chưa chạy, khởi động `python capcut_server.py`
   trong thư mục VectCutAPI (mặc định `~/tools/VectCutAPI`) (chạy nền) rồi kiểm lại.
2. Gom các track:
   - hình không tiếng;
   - giọng (`*_voice.wav` trong thư mục `_work`);
   - nhạc (`tach/music.wav` hoặc nhạc gốc);
   - phụ đề `.srt`.
   Thiếu stems thì tách bằng `demucs_split.py`.
3. Viết spec theo `capcut_api.py --help`. Tên bản nháp mới, không trùng: `<TEN>_<giong>_v1`.
   Chạy `python scripts/capcut_api.py build --spec <spec.json>`.
4. Xác nhận thư mục nháp đã có trong `com.lveditor.draft`, rồi báo người dùng mở CapCut tìm bản nháp đó.
   Lưu ý thêm: nhạc trong nháp chưa có ducking tự động.
