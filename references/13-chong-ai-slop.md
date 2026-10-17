# 13. Chống "AI slop" - soi logic rồi mới sửa

"AI slop" là thứ trông như phim/kịch bản nhưng rỗng: câu sáo, khẳng định không có căn cứ, số liệu bịa, nhịp câu đều như máy,
chuyển cảnh trang trí ở mọi chỗ, chữ trên mọi cảnh, cảnh tự chọn không đúng nội dung. Lớp này bắt chúng bằng **đo tất định trước**,
chỉ dùng Claude cho phần đã bị gắn cờ, và **không bao giờ nhận bản sửa mà chưa đo lại**.

## 1. Nguyên tắc

1. **Đo trước, LLM sau.** Hệ 0 (`slop_guard.py`) là quy tắc + từ điển + số học: chạy lại cho cùng kết quả, không tốn token.
   Claude (hệ 2) chỉ xem các mục hệ 0 gắn cờ, không duyệt lại cả phim.
2. **Không sửa âm thầm.** Hệ 0 chỉ gắn cờ kèm lý do và gợi ý. Mọi thay đổi đi qua bản sao + đo lại.
3. **Ba mức, không báo động tràn lan.** `chan` (phải sửa trước khi giao), `canh_bao` (nên sửa), `ghi_chu` (người xem xác nhận).
   Số chắc chắn sai -> chặn. Số chỉ khớp qua một phép suy -> ghi chú kèm phép suy, để người xác nhận.
4. **Chỉ số tách riêng.** Số có nguồn, sáo rỗng/100 chữ, từ đệm/100 chữ, độ dao động độ dài câu, độ dao động độ dài cảnh...
   Không gộp thành một "điểm AI" vì điểm gộp che mất chỗ hỏng.
5. **Người chấm khác người sửa.** Agent đề xuất sửa không được tự xác nhận. Bản sửa chỉ được nhận khi hệ 0 đo lại và thấy
   mục chặn giảm, không có lỗi chặn mới, chỉ số không xấu đi (`compare`). Nghiêng về phía bắt nhầm hơn là bỏ sót.

## 2. Số liệu phải có gốc (cửa giao: số bịa = 0)

- Mỗi số trong lời đọc, chữ trên hình và đồ hoạ động phải:
  - có **nguyên văn** trong `facts` (chấp nhận làm tròn ít chữ số có nghĩa: 3,5 từ 3,48; năm không bao giờ được làm tròn);
  - hoặc **suy ra một bước** từ số có nguồn: tổng/hiệu các phần, đổi đơn vị, tích/thương, phần trăm. Báo ở mức ghi chú kèm phép suy,
    vì có thể trùng ngẫu nhiên;
  - hoặc được khai rõ `[tính: 500 × 24 = 12.000]`. Phép tính được kiểm lại; toán hạng phải có nguồn hoặc là hằng số thông dụng (24, 60, 365...).
- Không đạt ba điều trên: `chan`. Sửa bằng cách thêm nguồn (câu gốc + tài liệu + ngày) vào facts, khai phép tính, hoặc bỏ số.
- Khẳng định so sánh nhất ("hàng đầu", "duy nhất", "đầu tiên", "lớn nhất"...) không kèm số có nguồn: chặn khi có facts.
- Chuẩn hoá Unicode NFC trước khi so (chữ Việt gõ tổ hợp khác dựng sẵn).

## 3. Dấu hiệu slop hệ 0 đo được

| Nhóm | Dấu hiệu | Ngưỡng mặc định |
|---|---|---|
| Lời | cụm sáo rỗng ("trong bối cảnh", "vươn tầm", "kỷ nguyên mới"...), từ đệm | mỗi câu có là gắn cờ; chỉ số /100 chữ |
| Lời | gạch dài "—", khuôn "không chỉ... mà còn" | mỗi lần |
| Nhịp | độ dài câu gần như nhau | hệ số biến thiên < 0,22 |
| Nhịp | 3+ câu mở đầu bằng cùng hai chữ | mỗi nhóm |
| Dựng | các cảnh dài gần bằng nhau | hệ số biến thiên < 0,12 |
| Dựng | một kiểu chuyển cảnh (không phải cắt) ở > 60 % điểm nối; 3+ chuyển cảnh trang trí | mỗi phim |
| Dựng | cùng một chuyển động máy ảo ở > 70 % cảnh; chữ trên > 70 % cảnh | mỗi phim |
| Dựng | mở đầu bằng thẻ màu trơn; nhiều giọng mà không có nhân vật | mỗi phim |
| Hình | cảnh do máy tự chọn theo mô tả | ghi chú: xem contact sheet |

Từ điển là danh sách riêng của repo, mở rộng theo dự án. Phong cách năng động/quảng cáo được nới mức chuyển cảnh trang trí.

## 4. Sổ luật khách (sửa một lần, nhớ mãi)

- Mỗi lần khách hoặc người duyệt sửa, chép **nguyên văn** câu sửa kèm người nói, ngày, phạm vi (`chung` / `khach:<ten>` / `du_an:<ten>`).
- Biên dịch thành luật kiểm được: `cam_chu` (regex cấm trong lời/chữ/phụ đề), `cam_nguon` (cấm loại nguồn hình), `giong_vung`, `toi_da_canh`.
  Luật không máy kiểm được thì để `khac`: hiện trong danh sách "cần người kiểm".
- Luật bị thay thì đánh dấu `thay_boi`, có `het_hieu_luc`; không xoá, để còn truy được vì sao.
- `slop_guard.py rules` báo độ phủ: bao nhiêu luật kiểm tự động được, luật nào lỗi regex. Mọi phim mới chạy lại toàn bộ sổ luật
  như bộ kiểm hồi quy.
- Sổ luật chứa thông tin khách, **để ngoài repo** (`~/.video_studio/luat/`). Repo chỉ có mẫu `templates/luat_khach.json`.

## 5. Vòng sửa (lệnh `/video:slop`)

1. Hệ 0 -> `SLOP_REVIEW.md`.
2. Agent mới, chỉ đọc, chỉ nhận các mục bị gắn cờ + facts -> JSON đồng ý/bác + câu viết lại.
3. Áp vào bản sao `_v2`.
4. `compare` bản gốc vs `_v2` -> NHẬN / KHÔNG NHẬN (kèm lý do). Tối đa 2 vòng, rồi đưa người dùng quyết.
5. Ghi lại những gì khách sửa tay vào sổ luật.

`make` tự chạy hệ 0 và ghi mục "Chống AI slop" vào `BAO_CAO_QC.md`. Đặt `"chan_khi_slop": true` để dừng dựng khi còn mục chặn.
`critic.py` dùng cùng bộ kiểm, nên phim nào cũng chỉ có một kết luận về số liệu.

## 6. Hiệu chỉnh

- Giữ `slop.json` của mỗi phim. Khi người duyệt bác một cờ (báo nhầm) hoặc khách bắt được lỗi hệ 0 bỏ sót, ghi lại.
  Sau vài phim, chỉnh ngưỡng/từ điển theo **cả hai phía**: tỷ lệ bắt đúng và tỷ lệ báo nhầm, không chỉ một phía.
- Bộ phân loại học máy (nếu dùng) chỉ là tầng phụ cho vùng lưng chừng, không thay hệ 0, và phải đo lại trên tiếng Việt trước khi tin.
- Ví dụ chạy được: `examples/vi_du_slop/` (bản gốc bị chặn -> bản sửa thêm năm không nguồn bị KHÔNG NHẬN -> bản sửa đúng được NHẬN).
