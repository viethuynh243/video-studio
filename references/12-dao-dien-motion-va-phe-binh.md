# 12 - Đạo diễn motion, phê bình độc lập, quy trình dự án lớn

Chưng cất từ 3 nguồn (10/2026):
- prompt "motion director & creative technologist" lan truyền trên X (Min Choi);
- skill mã nguồn mở [howseen-ai/claude-motion-design](https://github.com/howseen-ai/claude-motion-design) (MIT);
- một phiên dựng phim giới thiệu dự án cao tốc dài 8,5 phút, có bản đồ, Google Earth, 3D Blender và hiện trạng.

## 1. Tư duy "đạo diễn" trước khi viết code hay dựng

Phim chưa xong khi hết lỗi. Phim xong khi **đứng được cạnh tác phẩm tốt nhất cùng thể loại** và tham chiếu trong brief.

**Brief đạo diễn** (viết ra file `BRIEF.md`, chờ người dùng OK rồi mới dựng):
1. Thời lượng, khung gốc, các khung xuất từ CÙNG một timeline (16:9, 9:16, 1:1).
2. Chủ đề + **một lời hứa** (người xem nhớ đúng một điều gì).
3. Người xem, kênh phát.
4. **Phong cách tham chiếu có tên**, ví dụ "phim giới thiệu dự án của Bộ GTVT 2025", "Apple keynote bumper", "BBC Earth intro". Không chấp nhận mô tả chung chung kiểu "hiện đại, sang trọng".
5. **Các trạng thái có mốc thời gian**, ví dụ: 0-3 s hook → 3-12 s toàn cảnh → ... → kết logo.
6. **Danh sách lớp** (nền, hình, đồ hoạ, chữ, phụ đề).
7. **Kế hoạch âm thanh** (giọng, nhạc, SFX, chỗ im lặng).

**Facts** (`facts.md`): mỗi con số kèm câu gốc, nguồn, ngày. Không có `facts.md` thì không đưa số lên hình. `critic.py --facts` tự kiểm.
Dữ liệu minh hoạ phải ghi rõ "Minh hoạ" hoặc "Không theo tỉ lệ" trên hình.

## 2. Luật chống "chuyển động kiểu AI"

- MỘT màu nhấn. **Mỗi lúc chỉ một thứ chuyển động** (trừ khi một thứ dẫn dắt biến đổi liên tục).
- Một hệ hình khối từ đầu đến cuối. Ưu tiên biến đổi liền mạch thay vì cắt.
  Ví dụ: **tuyến đỏ là sợi chỉ xuyên suốt**: bản đồ 2D → Google Earth → 3D, tuyến luôn ở cùng vị trí trên màn hình nên chuyển cảnh liền.
- Lò xo có tắt dần (damping ≥ 0,72), vượt nhẹ, **không nảy kiểu hoạt hình**. Không chuyển động tuyến tính.
- Cấm:
  - gradient cầu vồng, hạt lấp lánh, chrome phát sáng;
  - emoji, lorem ipsum;
  - xoay 3D vô cớ;
  - chữ nhỏ không đọc được trên điện thoại.
- **Không khung chết**: không hình nào đứng im quá 0,5-1 s, trừ khung giữ cuối. Ảnh tĩnh luôn có trôi hoặc zoom nhẹ; thẻ chữ có ánh sáng trôi.
- Chữ trên hình: tối thiểu 0,3 s mỗi từ và ≥ 1,5 s tổng; luôn có ô nền. Chỗ hình đã nói rõ thì bỏ chữ.
- **Khung đầu tiên phải đẹp ngay**: không mở bằng nền trống. Mạng xã hội lấy khung 0 làm ảnh bìa.
- Cắt ở đỉnh vận tốc. Hai bên cắt cùng hướng và cùng tốc độ. Zoom giữ dấu của tốc độ phóng.

## 3. Đồ hoạ động bằng code (`scripts/motion_html.py`)

- Một file HTML vẽ mọi khung từ thời gian qua `window.seek(t)`:
  - không CSS transition, không timer, không `Math.random` (dùng PRNG có seed);
  - sau khi tải xong đặt `window.ready=true`.
- Render bằng Playwright, chờ 2 requestAnimationFrame sau mỗi `seek`.
- **Sub-frame motion blur tự động**: hình đứng thì 1 mẫu, chuyển động chậm 4, nhanh 8. Các mẫu trải trên nửa khoảng khung (màn trập 180°). **Không blur qua điểm cắt** (`--cuts`).
- Luôn chạy `stills` (4 ảnh tĩnh), xem, sửa rồi mới render cả đoạn. Có `--draft` 540p để duyệt nhịp.
- Mẫu có sẵn: `templates/motion/route_map.html` (bản đồ tuyến vẽ dần, mốc bật lò xo, ô số liệu) và `title_card.html` (thẻ chương, chữ trồi theo từng từ).
- Dùng trong project: `"nguon": {"html": "templates/motion/route_map.html", "params": {...}}`. `make` tự render, đặt vào cảnh và hoà cảnh như video.
- Thư viện tua được theo thời gian: Anime.js (`seek`), Theatre.js (`sequence.position`), GSAP (`totalTime`), Lottie (`goToAndStop`).
- Thư viện chỉ chạy theo thời gian thực thì không dùng được.

## 4. Vòng phê bình độc lập (`scripts/critic.py`, `/video:critic`)

1. **Người chấm khác người dựng**: một agent mới, chỉ đọc, mặc định kết luận "SỬA THÊM".
2. Tư liệu chấm:
   - `contact.png` (2 khung/s);
   - `phone.png` (360 px, kiểm đọc được trên điện thoại);
   - `strip_*.png` (12 khung quanh các đoạn chuyển động nhanh);
   - kiểm tra cứng: khung lạc, đen, chớp, khung chết, LUFS, chữ đủ lâu, số có nguồn.
3. Chấm /10: mở đầu 3 s · câu chuyện và sự thật · nhịp · chuyển động · hình ảnh · chữ · âm thanh · đồng bộ.
4. **Thử tắt tiếng**: chỉ nhìn khung hình, viết MỘT câu tóm tắt. Không viết được là phim trượt.
5. Ghi 3 lỗi nặng nhất, mỗi lỗi kèm mốc thời gian và cách sửa đo được.
6. Chỉ sửa hạng mục ≤ 7, không đụng hạng mục ≥ 9. Lặp đến khi mọi hạng mục ≥ 8, mỗi vòng dùng một agent mới, ghi nhật ký từng vòng.

## 5. Dự án lớn: phim giới thiệu dự án hạ tầng 5-10 phút

**Nguồn hình theo vai trò**

| Vai trò | Công cụ | Ghi chú |
|---|---|---|
| Bay tuyến, toàn cảnh địa hình | Google Earth Studio (GES) | Mỗi shot render 3-5 phút, nét. Dùng cho mọi đoạn GES thể hiện được; xin ghi nguồn "Google Earth" |
| Vị trí, hướng tuyến, nút giao, rà soát | Bản đồ 2D động (`motion_html.py`) | Ranh giới hành chính chính thức do khách cấp; ghi "không theo tỉ lệ" nếu minh hoạ |
| Cầu, hầm, nút giao, mặt cắt (chưa xây) | 3D Blender từ bản vẽ DXF | Đúng hình học bản vẽ; kiểm mái taluy, độ dốc nhánh; render GPU (OptiX, `cycles.device=GPU`, `use_persistent_data`) |
| Hiện trạng (đường cũ, sạt lở, đô thị) | Clip tư liệu | Bỏ logo đài, chữ chạy; **ghi đúng địa danh và năm quay**; xin phép bản quyền từng nguồn |
| Con người, thi công | Quay thật | Theo `references/11` |

**Vận hành**
- Ổ ngoài USB chập chờn khi ghi nặng kéo dài. Đặt **phần ghi nặng (khung render, cache, file tạm, mp4 nháp) lên ổ NVMe trong máy**.
  Mã nguồn và dữ liệu vào để ở ổ dự án. Chép sản phẩm về bằng `robocopy` chỉ-thêm (không xoá).
  Sau sự cố mất ổ, quét chỉ-đọc (`Repair-Volume -Scan` / `chkdsk /scan`) và kiểm lại các file ghi quanh lúc mất ổ.
- GPU render và CPU dựng cảnh chạy song song: GPU render vị trí trước trong khi CPU dựng vị trí sau.
  Mỗi máy chỉ một tác vụ nặng cùng loại. Theo dõi `nvidia-smi` để chắc GPU thực sự được dùng: đã gặp Blender chạy nền dùng CPU, GPU chỉ 4 %.
- Mỗi bản dựng giao kèm:
  - bản **chỉ có nhạc** (`make` tự xuất `_chi_nhac.mp4`);
  - tờ soát 10-20 khung;
  - danh sách cảnh giữ chỗ;
  - ghi chú những chỗ người dùng phải tự xem và nghe.
- Ước lượng thời gian bằng bảng hạng mục: trạng thái, phần còn lại, phần chặn đường găng. Báo cả phương án rút ngắn.
  Ví dụ: tăng tỉ lệ cảnh GES, chỉ dùng 3D cho những gì GES không thể hiện được.

**Lời đọc**: tên tuyến ghép ("Địa danh A - Địa danh B") hay bị đọc liền. Viết "Địa danh A, Địa danh B" và nghe lại từng câu (`accuracy.py`).
Nhịp cắt quảng cáo 1,4-3,5 s **không** hợp phim báo cáo; phim báo cáo dùng 3-7 s.

## 6. Quy tắc trung thực

- Không bịa số liệu, tính năng, công trình. Dữ liệu minh hoạ phải ghi rõ trên hình.
- Chú thích bài đăng phải đúng sự thật: không "làm trong 10 phút" nếu thực tế không phải vậy.
- Không dùng mặt hay giọng người thật khi chưa có đồng ý. Không dùng lại nhạc hay giọng của video tham chiếu.
