---
description: Lập kho cảnh từ thư mục footage - tách shot, chấm điểm (nét, sáng, mượt, rung, có người), tìm cảnh theo mô tả
argument-hint: <thư mục footage> [mô tả cảnh cần tìm, ví dụ "cầu dây văng nhìn từ trên cao lúc hoàng hôn"]
---

Dùng skill **video-studio** để quản lý kho cảnh. Yêu cầu: $ARGUMENTS

1. Quét kho: `python scripts/shot_select.py scan <thư mục> --out <thư mục>/kho_canh.json --sheet <thư mục>/kho_canh.jpg`.
   Thêm `--clip` nếu cần tìm theo mô tả (tải CLIP ~600 MB một lần).
2. Xem `kho_canh.jpg` (60 cảnh điểm cao nhất), mô tả ngắn từng nhóm cảnh.
3. Lọc cảnh tốt nhất:
   - `shot_select.py best kho_canh.json --min-dur 3 [--moving|--static]`;
   - tìm theo nội dung: dịch mô tả sang tiếng Anh, chạy `shot_select.py search kho_canh.json "<english>"`.
4. Trả bảng: file, mốc vào-ra, thời lượng, điểm, lý do (nét/mượt/rung/có người). Các mốc dùng thẳng được cho `nguon` trong project.json.
5. Cảnh điểm thấp (mờ, rung, giật nhịp, cháy sáng) thì ghi rõ để tránh dùng. Cảnh giật nhịp có thể cứu bằng `/video:fix`.
