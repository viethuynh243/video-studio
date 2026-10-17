# 05 - Âm thanh và giọng đọc

## 1. Chọn giọng đọc tiếng Việt

Người dùng Việt rất nhạy với giọng vùng miền. "Giọng Bắc" = phát âm Hà Nội chuẩn (phân biệt r/d/gi, s/x, tr/ch,
thanh hỏi/ngã). Phim doanh nghiệp/dự án mặc định **nam, Bắc, trang trọng**.

### Nguồn giọng đã thử (10/2026)

| Nguồn | Kết quả | Ghi chú |
|---|---|---|
| **VieNeu-TTS v3 Turbo** (`pip install vieneu`, Apache 2.0, chạy CPU/ONNX, ~2 s/câu) | **Tốt nhất.** 25 giọng có nhãn vùng miền/phong cách | Thiện Minh (nam, Bắc, kể chuyện) được chọn sau vòng nghe thử thực tế; Minh Đức (tin tức), Phạm Tuyên (trầm) cũng đọc đúng 100 % |
| Edge TTS (`edge-tts`) | Chỉ NamMinh, HoaiMy | Khách nghe NamMinh là giọng Nam ("giọng nam kì") - **không dùng khi cần giọng Bắc** |
| CapCut web TTS (12 giọng Việt) | Nam yếu: Anh Dũng/Trung Caha nghiêng Nam; "Duy Bắc" đọc sai thanh nhiều | Chí Mai (nữ) đạt; thao tác web rất chập chờn (xem `07-capcut.md`) |
| FPT.AI, Viettel AI, Zalo AI, Vbee | Có giọng nam Bắc thương mại | Cần tài khoản/khoá API do người dùng tự cấp |
| F5-TTS-Vietnamese, viXTTS | Nhân bản giọng từ 3-10 s mẫu | Chỉ nhân bản giọng có quyền dùng; viXTTS kém với câu < 10 từ |

Danh sách giọng VieNeu (`Vieneu().list_preset_voices()`): nam Bắc - Thiện Minh (kể chuyện), Minh Đức (tin tức),
Phạm Tuyên, Hải Đăng, Xuân Vĩnh, Quốc Tuấn, Thanh Bình (kể chuyện), Thiền Tâm Đức (kể chuyện, chậm), Adam bựa;
nữ Bắc - Mai Anh (tin tức), Trúc Ly, Ngọc Huyền, Ngọc Linh, Đoan Trang, Quỳnh Anh; Trung - Quang Sơn, Ngọc Trân;
Nam - Thái Sơn, Minh Triết (tin tức), Đức Trí, Adam, Thùy Dung (tin tức), Thục Đoan, Mỹ Duyên, Kim Thanh.

### Cách chọn có căn cứ
1. Sinh **cùng một đoạn kịch bản thật** bằng 4-8 giọng ứng viên (`tts_vi.py --voices ...`).
2. Đo `speech_check.py`: độ khớp lời (Whisper) - giọng đọc sai thanh sẽ bị nhận sai hàng loạt; loại giọng < 97 %.
3. Phân loại phương ngữ chỉ để **tham khảo** (mô hình `thangtrungnguyen/vietnamese-regional-accent-classification-model`
   chấm giọng tổng hợp thiếu ổn định, ví dụ chấm Minh Đức là Nam dù nhà phát triển ghi Bắc).
4. Gửi người dùng nghe các mẫu đạt, đặt tên file `1_Nam_Bac_<Ten>_<phongcach>.mp3`, để họ chọn. Lưu **tất cả** giọng đã sinh.

## 2. Chuẩn hoá chữ trước khi đọc (tiếng Việt)

| Viết | Vấn đề | Viết lại |
|---|---|---|
| `ki-lô-mét`, `Hà Nội – Hải Phòng`, `2021-2030` | Gạch nối/gạch ngang bị đọc thành **"đến"** | `ki lô mét`; `Hà Nội, Hải Phòng`; `2021 đến 2030` (khi đúng nghĩa "đến") |
| `100 km/h` | Đọc lộn xộn | `một trăm ki lô mét trên giờ` |
| `119 km` | Tuỳ engine | Viết chữ số bằng chữ cho câu quan trọng |
| Viết tắt (tên công ty, `BIM`, `FIDIC`) | Đọc từng chữ hoặc sai | Kiểm từng engine; viết phiên âm nếu cần (thử cách viết phiên âm, nghe lại) |
| Câu > 30 từ | Hụt hơi, ngắt sai | Tách câu ở dấu phẩy tự nhiên |

`tts_vi.py` tự áp các luật này (`--no-normalize` để tắt).

## 3. Đặt lời vào video

- Mỗi câu một file; đặt vào **khung thời gian (slot)** của lời gốc/kịch bản (bắt đầu = mốc gốc + 0,05 s).
- Câu dài hơn slot: tăng tốc ≤ 8 % (`atempo`), quá nữa thì sửa câu chữ, không ép.
- Câu ngắn hơn slot nhiều: có thể giảm tốc 5-6 % (rubberband, giữ formant) cho chậm rãi trang trọng.
- Fade 20 ms hai đầu mỗi câu để không lách tách.

## 4. Chuỗi xử lý giọng (broadcast)

```
highpass=f=75, equalizer=f=180:t=q:w=1.2:g=1.5 (ấm), equalizer=f=3200:t=q:w=1:g=1.5 (rõ),
deesser=i=0.35, acompressor=threshold=-20dB:ratio=2.5:attack=8:release=120:makeup=2,
loudnorm=I=-17:TP=-2:LRA=6 (từng câu)
```

## 5. Nhạc nền

- Nhạc đã trộn lẫn giọng cũ → tách bằng Demucs `htdemucs_ft` (`demucs_split.py`, dùng Python API; CLI từng lỗi thiếu `sphn`).
- **Giữ tốc độ gốc của nhạc.** Nếu buộc phải đổi độ dài, dùng rubberband (giữ cao độ) và tính lại mốc logo/điểm nhấn
  (`mốc_mới = mốc_gốc / hệ_số`). Khách từng chê nhạc "chạy nhanh quá" khi tempo bị đổi.
- Nối nhạc: crossfade ≥ 2 s tại chỗ cùng phách, cùng mức âm lượng (đo 1 s trước/sau).
- Ducking: `sidechaincompress=threshold=0.02:ratio=5:attack=60:release=700` - nhạc lùi ~6-8 dB khi có lời.

## 6. Mức âm lượng giao

| Nơi phát | Integrated | True Peak |
|---|---|---|
| YouTube/Facebook/mạng xã hội | -14 đến -16 LUFS | ≤ -1 dBTP |
| Trình chiếu hội trường, phim doanh nghiệp | -16 LUFS | ≤ -1,5 dBTP |
| Phát sóng (EBU R128) | -23 LUFS ±0,5 | ≤ -1 dBTP |

Đo: `ffmpeg -i out.mp4 -af ebur128=peak=true -f null -` (đọc `I:` và `Peak:` ở phần Summary).

## 7. Kiểm tra cuối phần âm thanh

- Whisper trên **rãnh giọng riêng** (không phải bản trộn - nhạc làm Whisper "bịa" chữ ở đoạn chỉ có nhạc).
- Nghe điểm nối câu, điểm crossfade nhạc, 2 s cuối (nhạc không bị cắt cụt).
- Không còn sót giọng cũ (kiểm phổ đoạn giữa các câu).
