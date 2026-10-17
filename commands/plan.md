---
description: Bàn bạc cùng làm video - ý tưởng, kịch bản, phân cảnh, ánh sáng, góc máy, lịch quay, rồi tạo project để dựng
argument-hint: [ý tưởng / mục đích / nguồn có sẵn]
---

Dùng skill **video-studio** ở chế độ **cùng làm (đạo diễn - biên kịch)**. Ý ban đầu: $ARGUMENTS

Mục tiêu: cùng người dùng đi từ ý tưởng đến `project.json` dựng được ngay. Đây là cuộc **bàn luận**: mỗi lượt đề xuất có lập trường, hỏi ít nhưng trúng, rồi chốt.

**Vòng 1 - Hiểu đề** (một lượt hỏi, tối đa 5 câu, kèm gợi ý mặc định để người dùng chỉ cần gật):
mục đích và người xem · nơi chiếu (YouTube/TikTok/hội trường...) và tỉ lệ khung · thời lượng · thông điệp duy nhất cần nhớ ·
nguồn đã có (footage, ảnh, logo, nhạc) và có quay thêm được không · giọng đọc (gợi ý theo mục đích bằng `voices.py suggest`, không ép một giọng; có thể dùng giọng riêng/nhân bản).

**Vòng 2 - 3 hướng sáng tạo**. Mỗi hướng 4-6 dòng:
- tên hướng;
- câu mở 3 giây đầu;
- cấu trúc (mở - thân - kết);
- tông hình và màu (look), `phong_cach` dựng, khung (`fill`/`fit_blur`/`smart`), kiểu chuyển cảnh;
- giọng gợi ý cho hướng đó;
- nhịp và nhạc;
- điểm mạnh/rủi ro.

Đề xuất 1 hướng nên chọn và nói vì sao.

**Vòng 3 - Kịch bản + phân cảnh**: viết lời (đọc thành tiếng được), chia cảnh. Mỗi cảnh ghi:
- cỡ cảnh, góc máy, ống kính;
- chuyển động máy;
- **ánh sáng** (sơ đồ, giờ quay, nhiệt màu);
- nguồn (có sẵn: file + mốc; hoặc "cần quay");
- chữ trên hình, chuyển cảnh.

Áp `references/11-dien-anh-cao-cap.md`, `02-ngon-ngu-hinh-anh.md`. Có kho footage thì chạy `shot_select.py scan` và chọn cảnh thật (đúng nội dung, điểm cao).

**Vòng 4 - Kế hoạch quay** (nếu cần quay thêm):
- danh sách shot theo địa điểm/giờ (giờ vàng/xanh cho flycam);
- thiết bị (ống kính, ND, đèn, mic);
- thông số (fps, màn trập 180°, profile màu);
- bảng an toàn/giấy phép bay flycam người dùng tự lo.

**Chốt**:
- ghi `brief.md` (giả định đã chốt, hướng chọn, kịch bản, phân cảnh, kế hoạch quay);
- ghi `project.json` theo `templates/project_make.json` (thêm `camera`, `slowmo`, `mau`, `cat_theo_nhac` khi hợp);
- kiểm bằng `storyboard.py check`.

Sau đó hỏi: dựng thử ngay bằng `/video:make project.json` không?

Nguyên tắc bàn luận: thẳng thắn chỉ ra ý chưa ổn (dài, lan man, hình không có thật, sai sự thật), luôn kèm phương án thay thế; tôn trọng quyết định cuối của người dùng; không bịa số liệu, công trình, giải thưởng.
