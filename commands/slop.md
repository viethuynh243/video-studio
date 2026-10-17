---
description: Soi "AI slop" trong kịch bản/dựng (sáo rỗng, số không nguồn, khẳng định suông, nhịp đều máy, luật khách) - Claude đề xuất sửa, đo lại độc lập rồi mới nhận
argument-hint: <project.json | kich_ban.txt> [facts.md ...] [luat.json ...]
---

Dùng skill **video-studio**, đọc `references/13-chong-ai-slop.md`. Đầu vào: $ARGUMENTS

1. **Hệ 0 - đo tất định (không LLM)**: chạy
   `python scripts/slop_guard.py review <project|kich_ban> <thu_muc>_slop --facts <facts...> --rules <luat...>`
   (hoặc tool MCP `slop_check`). Project có khoá `facts` / `luat` thì tự dùng.
   - Kết quả: `SLOP_REVIEW.md` + `slop.json`, mỗi phát hiện có mức **chặn / cảnh báo / ghi chú**, loại, câu, lý do, gợi ý.
   - Chỉ số để riêng từng cái (số có nguồn, sáo rỗng/100 chữ, từ đệm/100 chữ, độ dao động câu, độ dao động cảnh) - không gộp thành một điểm.
   - `ĐẠT` -> báo người dùng, dừng.
2. **Hệ 2 - người duyệt mù**: nếu `CHẶN` hoặc `CẦN XEM`, tạo một Agent **mới**, chỉ đọc (subagent_type `general-purpose`), chỉ giao:
   - `SLOP_REVIEW.md` (các câu/cảnh bị gắn cờ) và `facts` - không giao lập luận của người dựng, không giao cả project;
   - yêu cầu đúng phần "Việc của người duyệt" trong file: đồng ý/không (báo nhầm thì nói vì sao), viết lại câu hoặc đề xuất đổi cảnh;
   - không thêm số liệu mới không có nguồn, câu phải đọc thành tiếng được;
   - trả JSON `[{"o", "dong_y", "ly_do", "viet_lai"}]`, không sửa file nào.
3. **Áp bản sửa vào BẢN SAO**: `project_v2.json` / `kich_ban_v2.txt` (không ghi đè bản gốc). Mục người duyệt bác (`dong_y: false`) thì giữ nguyên và ghi lý do.
4. **Đo lại độc lập**: `python scripts/slop_guard.py compare <ban_goc> <ban_v2> --facts ... --rules ...` (hoặc MCP `slop_compare`).
   - `NHẬN` khi mục chặn giảm, không sinh lỗi chặn mới, chỉ số tỷ lệ không xấu đi.
   - `KHÔNG NHẬN` -> giữ bản gốc, đưa cả hai cho người dùng xem kèm lý do. Tối đa 2 vòng.
   - Người duyệt **không bao giờ tự xác nhận** bản sửa của chính mình.
5. **Ghi luật khi người dùng/khách sửa tay**: chép **nguyên văn** câu sửa vào sổ luật để phim sau tự kiểm:
   `python scripts/slop_guard.py ghi ~/.video_studio/luat/<khach>.json --nguon "<câu nguyên văn>" --loai cam_chu --mau "<regex>" --pham-vi khach:<khach>`
   Sổ luật để **ngoài repo**. Luật cũ bị thay thì dùng `--thay L00x` (đánh dấu, không xoá). `slop_guard.py rules <so_luat>` xem bao nhiêu luật kiểm tự động được.
6. Báo người dùng: kết luận trước/sau, bảng chỉ số trước/sau, các câu đã viết lại, mục bị bác, mục cần người xem bằng mắt/tai (cảnh tự chọn, số suy ra, số làm tròn).
