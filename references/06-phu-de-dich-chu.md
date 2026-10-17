# 06 - Phụ đề, bản dịch, chữ trên màn hình

## 1. Bản dịch

- Dịch theo **nghĩa và ngữ cảnh** của bản gốc, không dịch từng chữ. Đối chiếu từng câu: số liệu, tên riêng,
  chức danh, năm, tần suất ("2 năm một lần" ≠ "hằng quý").
- Tên riêng tiếng Việt: viết không dấu theo cách quốc tế quen dùng (Hanoi, Hai Phong, Ho Chi Minh City, Hai Van).
- Ghi các điểm còn phân vân thành câu hỏi riêng cho khách (ví dụ "65 years" hay "more than six decades").
- Ngôn ngữ máy không kiểm được (tiếng Lào với Whisper) → nói rõ là chưa kiểm được bằng máy.

## 2. Dấu câu trong phụ đề

- **Không dùng gạch dài "—"** trong phụ đề (khách thấy như dấu gạch chéo). Thay bằng dấu phẩy, hai chấm, hoặc tách câu.
- Gạch nối ngắn "–" giữa địa danh trong tên tuyến được giữ: "Hanoi–Hai Phong–Ha Long", "Quy Nhon–Chi Thanh".
- Kiểm tự động: `grep -n "—" *.srt *.ass` phải rỗng.

## 3. Định dạng phụ đề

| Mục | Chuẩn |
|---|---|
| Số dòng | ≤ 2 dòng |
| Độ dài dòng | ≤ 42 ký tự (Latin); chữ Lào/Thái tính theo độ rộng hiển thị |
| Tốc độ đọc | ≤ 17 ký tự/giây (người lớn), ≤ 15 cho khán giả rộng |
| Thời gian hiện | 1-7 s mỗi phụ đề; khoảng nghỉ giữa hai phụ đề ≥ 2 khung |
| Ngắt dòng | Ngắt theo cụm nghĩa, không tách tính từ khỏi danh từ, không để một từ lẻ dòng hai |
| Đồng bộ | Vào theo lời ±0,1 s; ra không quá 0,5 s sau lời |
| Vị trí | Đáy, trong safe zone; tự đẩy lên khi chạm chữ trên hình |

Style ASS gợi ý (1080p): font Arial/Noto Sans (có glyph Lào: Noto Sans Lao), cỡ 46-52, chữ trắng, viền 2-3 px đen,
bóng 1, MarginV 60. Phụ đề **không chạm chữ có sẵn trên hình** - kiểm bằng contact sheet ở các mốc có chữ.

## 4. Kiểm phụ đề khớp kịch bản

So nội dung ghép của mọi sự kiện phụ đề (bỏ khoảng trắng) với văn bản đã duyệt: phải **100 %**.
Số sự kiện, tổng ký tự ghi vào báo cáo. Xuất `.srt` từ `.ass` để giao kèm.

## 5. Chữ trên màn hình (TOS) và đồ hoạ thuyết minh

- Tiêu đề cùng kiểu, cùng màu với đồ hoạ gốc của khách; không chói.
- Con số trên đồ hoạ **chỉ lấy từ lời đọc**; số không có trong lời → hỏi khách trước.
- Bản đồ: dùng ranh giới hành chính chính thức do khách cấp (vấn đề chủ quyền, không tự vẽ).
- Hiệu ứng nhóm A cho phim doanh nghiệp: mốc năm, thanh lĩnh vực, bản đồ tuyến vẽ dần, danh sách công trình sáng
  dần theo lời, tường ảnh (collage) ở vế liệt kê. Màu nhấn trắng/cyan hoặc theo khách.
