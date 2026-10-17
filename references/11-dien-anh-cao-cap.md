# 11 - Kỹ thuật điện ảnh cao cấp: ánh sáng, ống kính, góc máy, chuyển động, màu, âm thanh, dựng

Dùng khi lập kế hoạch quay (`/video:plan`), viết storyboard, chọn cảnh, hoặc giải thích vì sao một cảnh "trông rẻ".
Mỗi mục: **làm gì - khi nào - con số cụ thể**.

## 1. Ánh sáng

### 1.1 Sơ đồ cơ bản
| Sơ đồ | Cách đặt | Dùng cho |
|---|---|---|
| **3 điểm** | Key 30-45° lệch trục máy, cao hơn mắt 30°; Fill phía đối diện yếu hơn key 1-2 stop; Back/Rim sau lưng chéo 135° | Phỏng vấn, lãnh đạo phát biểu - chuẩn doanh nghiệp |
| **Rembrandt** | Key 45° bên, 45° cao - tam giác sáng dưới mắt phía tối | Chân dung có chiều sâu, trang trọng |
| **Loop** | Key 30° bên, hơi cao - bóng mũi nhỏ chéo xuống | Phỏng vấn thân thiện, dễ dùng nhất |
| **Butterfly (Paramount)** | Key chính diện trên cao, bóng cánh bướm dưới mũi; tấm hắt dưới cằm | Nữ, beauty, chân dung sang |
| **Split** | Key 90° ngang | Kịch tính, bí ẩn - tránh cho phim doanh nghiệp |
| **Broad / Short** | Chiếu mặt phía gần máy (broad) / phía xa máy (short - làm gầy mặt, sâu hơn) | Short light là mặc định đẹp cho phỏng vấn |

### 1.2 Tỉ lệ tương phản (key:fill)
2:1 (1 stop) - sáng sủa, quảng cáo · 4:1 (2 stop) - phim doanh nghiệp cao cấp, có khối · 8:1 (3 stop) - điện ảnh, low-key.

### 1.3 Chất lượng ánh sáng
- **Mềm**: nguồn lớn và gần (softbox 90-120 cm, khung khuếch tán 1,2-2,4 m, hắt trần). Da đẹp, ít bóng gắt.
- **Cứng**: nguồn nhỏ/xa (mặt trời trưa, đèn trần). Chỉ dùng có chủ ý (rim, hiệu ứng).
- **Negative fill**: tấm đen phía fill để khối mặt rõ hơn - mẹo "điện ảnh hoá" rẻ nhất.
- **Motivated light**: mọi nguồn sáng phải có lý do trong cảnh (cửa sổ, đèn bàn). Đèn trong khung (practicals) ấm 2700-3200 K tạo chiều sâu.
- **Background**: nền tối hơn chủ thể 1-2 stop; thêm vệt sáng/màu trên nền để tách lớp.

### 1.4 Nhiệt màu
Nến 1900 K · đèn sợi đốt 2700-3200 K · ánh nắng trưa 5600 K · trời râm 6500-7500 K · bóng râm/xanh 8000 K+.
Không trộn nhiệt màu trên mặt người trừ khi có chủ ý (cửa sổ xanh + đèn ấm = phim, nhưng phải cân trên da).
Cân trắng theo key light; da người là chuẩn khi chỉnh màu.

### 1.5 Ánh sáng tự nhiên & flycam công trình
- **Giờ vàng** (khoảng 1 giờ sau bình minh / trước hoàng hôn): bóng dài, khối công trình nổi, màu ấm - cảnh mở đầu/kết.
- **Giờ xanh** (20-40 phút sau hoàng hôn): đèn cầu/đường bật, trời xanh đậm - cảnh "tầm nhìn", đêm hiện đại.
- Trưa nắng gắt: quay top-down, mặt đường; tránh mặt đứng công trình (bóng xấu).
- Ngày râm: phù hợp quay cận chi tiết, người làm việc; trời trắng thì giấu bầu trời khỏi khung.
- Mặt nước/kính: xoay góc để tránh lóa; CPL (lọc phân cực) giảm phản chiếu, tăng trời xanh.

## 2. Ống kính, khẩu, màn trập

| Tiêu cự (full-frame) | Cảm giác | Dùng |
|---|---|---|
| 14-24 mm | Rộng, phóng đại không gian, méo cạnh | Nội thất, công trường, flycam |
| 28-35 mm | Tự nhiên, "nhìn bằng mắt người đi cùng" | Handheld, đời thường, tour |
| 50 mm | Trung tính | Trung cảnh, phỏng vấn rộng |
| 85-135 mm | Nén hậu cảnh, xoá phông đẹp | Phỏng vấn cận, chân dung, chi tiết |
| 200 mm+ | Nén mạnh (xe dồn sát, mặt trời to) | Giao thông, cầu xa, hoàng hôn |

- **Khẩu**: f/1.8-2.8 xoá phông (phỏng vấn, chi tiết); f/4-5.6 nhóm người; f/8 phong cảnh/kiến trúc (nét sâu).
- **Luật màn trập 180°**: tốc độ = 1/(2 × fps): 24p → 1/50, 25p → 1/50, 30p → 1/60, 60p → 1/120. Ngoài trời phải dùng **ND** để giữ màn trập này, nếu không chuyển động sẽ "lấp lánh" giật.
- **Slow motion**: quay 50/60p (chậm 2×) hoặc 100/120p (chậm 4-5×) rồi đặt vào timeline 24/25p - `fps_convert.py --slowmo`. Ánh sáng cần gấp 2-4 lần.
- **ISO**: giữ ở ISO gốc của máy (dual native ISO) để ít nhiễu nhất.
- **Profile log** (S-Log3, V-Log, D-Log): cần LUT chuyển đổi + phơi sáng đúng (da khoảng +1 stop so với mức trung tính trên waveform).

### 2.1 Thiết lập phơi sáng theo tình huống (máy mirrorless/cinema full-frame, 24/25p)

Tam giác phơi sáng: **màn trập** cố định theo luật 180° (chuyển động), **khẩu** theo độ sâu trường ảnh mong muốn (kể chuyện), **ND** bù sáng, **ISO** ở mức gốc (nhiễu). Chỉnh theo thứ tự: fps → màn trập → khẩu → ND → ISO cuối cùng.

| Tình huống | fps / màn trập | Khẩu | ISO | ND / ghi chú |
|---|---|---|---|---|
| Flycam công trình ban ngày | 25p · 1/50 (hoặc 50p · 1/100 nếu cần slow-mo) | f/2.8-4 (cảm biến drone nhỏ, nét sâu sẵn) | 100 | ND16-ND32 nắng trưa, ND8 giờ vàng; quay D-Log/Log, phơi lệch phải nhẹ |
| Flycam giờ xanh / đêm (cầu bật đèn) | 25p · 1/50 | mở hết | 400-1600 (không quá ISO tối đa sạch của drone) | bay chậm, tránh xoay nhanh (mờ/nhiễu); dùng hyperlapse nếu quá tối |
| Phỏng vấn trong nhà (3 điểm) | 25p · 1/50 | f/2-2.8 (85 mm), f/4 nếu 2 người | ISO gốc (vd 800/4000 dual-ISO) | key softbox, fill -1 đến -2 stop, rim; cân trắng theo key 3200/5600 K |
| Hội nghị, hội trường | 25p · 1/50 (đèn LED nhấp nháy: thử 1/50, 1/60, 1/100 để hết sọc) | f/2.8-4 | 800-3200 | tôn trọng nhiệt màu sân khấu; ống 70-200 mm cho cận người phát biểu |
| Người làm việc tại hiện trường (nắng) | 25p · 1/50 | f/4-5.6 | 100 | ND6-ND8 stop; quay ngược sáng có tấm hắt / fill; tránh trưa gắt |
| Chi tiết thiết bị, sản phẩm | 25p · 1/50 | f/2.8 (macro f/5.6-8 để đủ nét) | gốc | slider/motion control; đèn mềm + rim |
| Slow motion 2-5× | 50p · 1/100, 100/120p · 1/200-1/240 | như trên | tăng 1-2 stop hoặc thêm đèn | ánh sáng nhân tạo phải không nhấp nháy (high-CRI, flicker-free) |
| Timelapse tiến độ thi công | ảnh 1 tấm / 2-10 s, màn trập dài (ND) cho chuyển động mượt | f/8 | 100 | khoá phơi sáng + cân trắng tay (tránh nhấp nháy), chân máy cố định |
| Đêm thành phố, vệt đèn xe | 25p · 1/50 (video) / ảnh 2-15 s | f/8-11 | 100-400 | chân máy, tắt chống rung ống kính khi trên tripod |

Mẹo: **Zebra 95-100 %** báo cháy sáng, **false color** cho da (~55-70 IRE), **focus peaking** khi lấy nét tay; quay **log** khi chênh sáng lớn, còn lại profile chuẩn (Rec.709) cho nhanh hậu kỳ.

### 2.2 Viết prompt điện ảnh cho video AI (Veo, Kling, Sora, Seedance, Wan)

Cấu trúc ổn định: **Chủ thể → Bối cảnh → Hành động (một hành động nhỏ) → Ánh sáng → Phong cách/ống kính → Chuyển động máy (cuối câu)**.
- Mỗi shot: **một cỡ cảnh, một chuyển động, một ống kính**, 2-3 bổ ngữ. Ví dụ: *"medium close-up of an engineer reviewing drawings at a site office, warm window light from the left, shallow depth of field, 85mm lens, slow dolly in"*.
- Gọi tên ánh sáng cụ thể: *soft morning light, golden hour backlight, overcast soft light, warm practical lamps with deep shadows, blue hour city lights*.
- Từ khoá ống kính/khẩu được hiểu như mô tả hình (không phải thông số thật): *24mm wide, 35mm, 85mm portrait, telephoto compression, shallow depth of field, deep focus, anamorphic flare*.
- Màn trập/fps: *natural motion blur, 180-degree shutter look, ultra slow motion*. ISO: *clean, low noise* / *gritty film grain*.
- Chuyển động máy theo model: Kling theo lệnh camera chặt nhất (ghi rõ chuyển động); Veo mạnh về cảnh tự nhiên và chuyển động môi trường; tránh chồng nhiều chuyển động trong 1 prompt.
- Giữ nhất quán series: cùng câu mô tả nhân vật/trang phục, cùng ảnh tham chiếu, cùng seed (xem `09-phim-ai-pipeline.md`).

Nguồn tham khảo: [Artlist - prompting tips Kling/Veo/Sora/Seedance](https://help.artlist.io/hc/en-us/articles/31558164653213), [Prompt Architects - direct AI video like a filmmaker](https://prompt-architects.com/blog/27-direct-ai-video-like-filmmaker), [AI video camera movement cheatsheet](https://lzyprompt.com/blog/ai-video-camera-movement-prompts/).

## 3. Góc máy và bố cục nâng cao

- **Chiều sâu 3 lớp**: tiền cảnh (cành cây, lan can, mép kính) - trung cảnh (chủ thể) - hậu cảnh. Thêm tiền cảnh mờ là cách nhanh nhất để hình "đắt".
- **Đường dẫn** (làn đường, dầm cầu, dây văng) hội tụ về chủ thể; **đối xứng** cho công trình (trục cầu, cổng); **khoảng trống âm** cho chữ.
- **Chiều cao máy**: ngang mắt = trung lập; thấp (low angle) = tầm vóc, công trình hùng vĩ; cao = tổng quan, nhỏ bé.
- **Hướng nhìn & khoảng thở**: chừa không gian phía người nhìn/xe chạy tới (lead room); headroom vừa đủ (mắt ở 1/3 trên).
- **Phỏng vấn**: người nhìn lệch ống kính 15-30° về phía có khoảng trống; máy B cận 85 mm góc 30-45° để cắt ghép; nền có chiều sâu và tối hơn.
- **Coverage một cảnh**: Wide (bối cảnh) → Medium (hành động) → Close (cảm xúc/chi tiết) → Insert (tay, thiết bị) → Cutaway (phản ứng, không gian). Dựng mới có đường lui.
- **Quy tắc 180°/30°**: giữ máy một phía trục hành động; hai cảnh liền nhau cùng chủ thể phải đổi góc ≥ 30° hoặc đổi cỡ cảnh ≥ 1 nấc (tránh jump cut).

## 4. Chuyển động máy (và bản "ảo" khi dựng)

| Chuyển động | Ý nghĩa | Tốc độ gợi ý | Làm ảo khi dựng |
|---|---|---|---|
| Push-in (dolly in) | Tập trung, nhấn mạnh | 3-8 % khung/giây | `camera: {move: push_in, amount: 0.06-0.10}` |
| Pull-out | Tiết lộ bối cảnh, kết | như trên | `pull_out` |
| Truck/pan ngang | Theo dõi, khoe chiều dài | pan hết khung trong ≥ 7 s (24p) để không strobe | `pan_left/right` |
| Tilt | Khoe chiều cao (trụ, tháp) | chậm, đều | `tilt_up/down` |
| Orbit (flycam vòng) | Công trình là nhân vật chính | 10-20°/s | - |
| Reveal (bay qua vật cản) | Mở đầu ấn tượng | | - |
| Crane/jib, pedestal | Sang trọng, sự kiện | | - |
| Dolly zoom (Vertigo) | Choáng, cao trào | hiếm dùng | - |
| Hyperlapse/timelapse | Thời gian, tiến độ thi công | 1 ảnh/2-5 s | - |
| FPV drone | Năng lượng, xuyên qua công trình | | - |

Luật: **mỗi shot một chuyển động, có điểm đầu và điểm dừng rõ** (ease in/out). Gimbal tốt hơn tay; tripod khi chủ thể đã động.
Pan quá nhanh ở 24p gây "strobing" - quay 50/60p rồi `fps_convert.py` xuống 24p có motion blur 180°.

## 5. Màu (grading)

1. **Correction trước, look sau**: cân trắng, phơi sáng, tương phản cho từng shot → khớp màu giữa các shot (`grade.py match`, `mau.khop_mau`) → look chung (`grade.py look`).
2. Da người là thước đo: dải màu da nằm trên "skin tone line" (vectorscope, khoảng 11 giờ).
3. Look gợi ý: **clean** (doanh nghiệp, trung thực), **filmic** (phim tài liệu cao cấp), **teal_orange** (quảng cáo năng động - nhẹ tay), **warm** (con người, truyền thống), **cool** (công nghệ, đêm).
4. Không đẩy bão hoà > 10 %, không để đen bị bết (giữ chi tiết vùng tối), highlight không cháy trắng trên mặt người.
5. **Color script**: mỗi chương một tông chủ đạo (quá khứ ấm/nhạt - hiện tại trung tính - tương lai xanh sáng).

## 6. Âm thanh điện ảnh

- **Room tone** 30 s mỗi bối cảnh để lấp chỗ cắt. **Foley/SFX** nhẹ (tiếng xe, gió, công trường) làm hình "sống".
- **J-cut / L-cut**: tiếng cảnh sau vào trước 0,5-1 s, hoặc tiếng cảnh trước kéo qua cắt.
- **Riser/whoosh** trước thẻ chương; **im lặng 0,5-1 s** trước câu quan trọng.
- Nhạc: đổi đoạn (verse → chorus) trùng thay đổi nội dung; cắt trên phách (`cat_theo_nhac`).
- Mic: lavalier + shotgun dự phòng; đầu thu -12 dBFS đỉnh lời nói; tránh phòng vang (rèm, thảm).

## 7. Dựng (editing) đẳng cấp

- **Quy tắc 6 của Walter Murch** (theo thứ tự quan trọng): cảm xúc 51 % > câu chuyện 23 % > nhịp 10 % > hướng nhìn 7 % > mặt phẳng 2D 5 % > không gian 3D 4 %.
- **Cắt trên hành động** (cut on action): cắt giữa động tác để che điểm nối.
- **Hiệu ứng Kuleshov**: ý nghĩa đến từ cặp hình; đặt cảnh phản ứng sau cảnh sự kiện.
- **Nhịp**: mở chậm (thiết lập) → nhanh dần (thông tin) → chậm lại (cảm xúc, kết). Phim doanh nghiệp: 2,5-7 s/shot; teaser 0,8-2 s.
- **Match cut** theo hình/chuyển động/màu; **montage** cho tiến độ thi công.
- 3 giây đầu quyết định người xem ở lại (mạng xã hội): hình mạnh nhất + câu hỏi/con số.

## 8. Định dạng & khung hình

16:9 (YouTube, trình chiếu) · 9:16 (TikTok/Reels/Shorts - `camera.py reframe`, chữ tránh 15 % trên/20 % dưới) ·
1:1, 4:5 (feed) · 2.39:1 letterbox (cảm giác điện ảnh - chỉ cho trailer/teaser, không cho phim thông tin nhiều chữ).
Quay 4K khi biết sẽ xuất dọc hoặc cần punch-in/virtual move - crop 1080 từ 4K không mất nét.

## 9. Checklist "cao cấp" trước khi giao

Ánh sáng có khối (không phẳng) · nền tách khỏi chủ thể · màn trập 180° (chuyển động tự nhiên) · không jump cut ·
mỗi shot một chuyển động có ease · màu khớp giữa các shot · da tự nhiên · J/L-cut ở chỗ chuyển ý · nhạc có cao trào đúng nội dung ·
3 giây đầu mạnh · chữ ít, sạch, đúng safe zone · LUFS đúng nền tảng.
