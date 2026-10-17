# 04 - Hình ảnh, màu, độ nét, xuất file

## 1. Chuẩn hoá hình

- Scale: `scale=1920:1080:flags=lanczos`; nguồn khác tỉ lệ → crop vào giữa (không méo, không viền đen) trừ khi
  là quay màn hình cần giữ trọn (khi đó nền mờ phía sau hoặc khung bo góc + đổ bóng trên nền gradient).
- Viền đen sẵn trong nguồn (letterbox): `cropdetect` rồi crop trước khi scale.
- Logo/watermark góc của nguồn: ưu tiên chọn đoạn khác; nếu buộc dùng thì crop phóng 5-8 % hoặc `delogo` vùng nhỏ.
- Interlace (nguồn cũ 50i/60i): `bwdif` (hoặc `yadif`) trước mọi thứ khác.
- Không upscale 720p lên làm cảnh chính; nếu bắt buộc: lanczos + `unsharp=5:5:0.6` nhẹ.

## 2. Màu

- Thống nhất màu giữa các nguồn trong một đoạn: cân trắng, độ tương phản, bão hoà gần nhau
  (`eq=contrast=..:saturation=..`, `colorbalance`, hoặc LUT `.cube` qua `lut3d`).
- Nguồn log (S-Log, D-Log, V-Log) phải áp LUT chuyển đổi trước khi chỉnh.
- Giữ dải màu chuẩn BT.709, `-color_primaries bt709 -color_trc bt709 -colorspace bt709`, giới hạn TV range.
- Không đẩy bão hoà quá (da người cam, trời xanh gắt). Phim doanh nghiệp: tươi, sạch, trung thực.

## 3. Đồ hoạ, chữ trên hình

- Bảng màu và font lấy từ đồ hoạ có sẵn của khách (thẻ chương, logo). Một màu nhấn cho phần tử đang được đọc.
- Chuyển động đồ hoạ: ease-in-out, fade vào ~0,6 s, ra ~0,5 s; không nảy, không xoay, không hạt sáng chạy.
- 1-2 phần tử đồ hoạ mỗi vế; tắt hẳn trước dissolve.
- Chữ dịch chèn trên slide: mờ nhẹ (opacity ~55-70 %), chỉ khi chữ đó chứa số liệu/thông tin lời đọc không nói.

## 4. Xuất file

| Mục đích | Thiết lập |
|---|---|
| Bản giao chính 1080p | H.264 High, `-crf 16 -preset slow -pix_fmt yuv420p -profile:v high -tune film`, GOP ≈ 2 s (`-g 48` ở 24p), `-movflags +faststart`; AAC 256-320 kbps 48 kHz stereo |
| YouTube | như trên; bitrate tham chiếu SDR 1080p24-30 ≈ 8 Mbps trở lên (CRF 16 thường cao hơn, tốt) |
| Mạng xã hội dọc | 1080×1920, safe zone UI: chừa ~15 % trên, ~20 % dưới, ~10 % phải |
| Lưu trữ/master | ProRes 422 HQ hoặc H.264 CRF 12, giữ PCM 48 kHz |
| Bản nháp gửi xem nhanh | CRF 23, 720p, file < 30 MB để gửi qua điện thoại |

- Phụ đề: giao cả bản **burn-in** (ASS) và file `.srt` rời.
- Kiểm lại sau xuất: thời lượng khớp, số khung đúng `fps × thời lượng`, không mất âm cuối (`-shortest` cắt nhầm).
