# 01 - Quy trình dự án, phiên bản, duyệt bản

## 1. Brief (hỏi một lần, gọn)

Chỉ hỏi những gì đổi được kết quả. Còn lại tự chọn mặc định và ghi vào mục "Giả định đã chốt" của báo cáo.

| Mục | Mặc định nếu không nói |
|---|---|
| Mục đích, người xem | Phim giới thiệu doanh nghiệp/dự án, người xem là đối tác, cơ quan quản lý |
| Nền tảng | YouTube/Facebook ngang 16:9 1920×1080 |
| Thời lượng | Theo kịch bản; câu đọc tiếng Việt ≈ 4,5-5,5 âm tiết/giây (giọng trang trọng) |
| Ngôn ngữ thuyết minh, phụ đề | Như bản gốc; bản dịch phụ đề ngôn ngữ còn lại |
| Giọng đọc | Nam, miền Bắc, phong cách tin tức/kể chuyện trang trọng |
| Nhạc | Giữ nhạc gốc (tách bằng Demucs nếu đã trộn sẵn), không đổi tốc độ nếu không bắt buộc |
| fps | Theo đa số nguồn; phim tài liệu/doanh nghiệp: 24 hoặc 25 |

## 2. Cấu trúc thư mục dự án

```
<Dự án>/
  nguon/            # file gốc, không bao giờ sửa
  lam_viec/         # file trung gian, cache, stems
  rev/              # báo cáo, bảng kiểm góp ý, ảnh soát
  <TEN>_v1.mp4 ...  # các bản dựng
  <TEN>.mp4         # bản chính đã duyệt
  <TEN>_luu_<mo_ta>.mp4  # bản chính cũ
```

File trung gian để trong scratchpad của phiên hoặc `lam_viec/`. Không ghi vào thư mục nguồn.

## 3. Phiên bản và duyệt

- Mỗi lần gửi = một bản `_vN` mới. Không sửa đè bản đã gửi.
- Người dùng duyệt ("đồng ý thay làm bản cuối") thì mới:
  ```bash
  mv -n TEN.mp4 TEN_luu_<mo_ta>.mp4 && cp -n TEN_vN.mp4 TEN.mp4 && cmp TEN.mp4 TEN_vN.mp4
  ```
- Phụ đề, `.ass`, `.srt`, stems đi kèm đổi tên theo cùng quy tắc.
- Giữ một file `rev/GOP_Y_DA_NHAN.md`: **mọi góp ý của khách thành một dòng kiểm**. Mỗi bản mới phải soát lại
  toàn bộ bảng này, không chỉ góp ý mới nhất (lỗi cũ hay quay lại khi dựng lại).

## 4. Báo cáo khi gửi bản

Ngắn, theo thứ tự:
1. Tên file, thời lượng, độ phân giải/fps.
2. Đã đổi gì so với bản trước (gạch đầu dòng, theo vế/mốc thời gian).
3. Số đo QC (độ giật, khung lạc, LUFS, độ khớp phụ đề/lời) - xem `08-qc-giao-file.md`.
4. Việc còn chờ khách quyết (mỗi việc một câu hỏi, có phương án đề xuất).
5. Bản cũ vẫn nguyên ở đâu.

Không báo "đã mượt/đúng" nếu chưa đo. Ghi rõ phần chưa kiểm được (ví dụ bộ nhận dạng không đọc được tiếng Lào).

## 5. Làm việc dài hơi

- Render nặng chạy nền, **một lượt một lúc** khi dùng chung thư mục cache (chạy song song từng gây PermissionError).
- Cache theo khoá (nguồn + mốc + tham số) để dựng lại một cảnh không phải render cả phim.
- Ghi nhật ký quyết định (cảnh nào thay vì sao) vào `rev/` để lần sau không lặp sai.
