---
description: Vòng phê bình độc lập - một agent mới (không tham gia dựng) chấm phim 1-10 theo 8 hạng mục, thử xem tắt tiếng, chỉ ra 3 lỗi nặng nhất
argument-hint: <video> [project.json] [facts.md]
---

Dùng skill **video-studio**. Phim cần chấm: $ARGUMENTS

1. Chạy `python scripts/critic.py <video> [--project project.json] [--facts facts.md]`. Lệnh này tạo `<video>_critic/` gồm:
   - `contact.png`, `phone.png`, `strip_*.png`;
   - `CRITIC.md`: kết quả kiểm tra cứng và bảng chấm.
2. **Người chấm phải khác người dựng**: tạo một Agent mới, chỉ đọc (subagent_type `general-purpose`), giao:
   - đọc `CRITIC.md` và xem các ảnh (Read);
   - chấm từng hạng mục /10 như một đạo diễn khó tính; mặc định kết luận là "SỬA THÊM";
   - **thử tắt tiếng**: chỉ nhìn ảnh, viết 1 câu tóm tắt phim; không viết được thì trượt;
   - liệt kê 3 lỗi nặng nhất, mỗi lỗi có mốc thời gian, mức độ và cách sửa đo được;
   - không sửa file nào.
3. Nhận kết quả, ghi vào `<video>_critic/vong_<n>.md` (nhật ký từng vòng).
4. Nếu chưa ĐẠT: chỉ sửa hạng mục ≤ 7, dựng lại thành bản `_v<n+1>`, rồi chấm lại bằng **một agent mới**. Lặp lại đến khi mọi hạng mục ≥ 8, tối đa 3 vòng, sau đó báo người dùng.
5. Báo cáo người dùng:
   - bảng điểm từng vòng;
   - câu tóm tắt khi xem tắt tiếng;
   - các lỗi đã sửa;
   - những chỗ người dùng cần tự xem và nghe.
