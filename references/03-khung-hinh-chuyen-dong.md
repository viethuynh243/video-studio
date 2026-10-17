# 03 - Khung hình và chuyển động: fps, nhịp, giật, khựng, khung lạc

Đây là phần khách phàn nàn nhiều nhất ("giật", "đơ", "khựng", "lia cam không smooth"). Mắt người thấy được
**độ không đều của chuyển động** rất nhỏ, nên phải đo bằng số, không đoán.

## 1. Chọn fps dựng

- Đếm fps của mọi nguồn (`probe_qc.py --inventory`). Dựng theo **fps của nguồn chính**:
  - đa số 24/23.976/25 → dựng 24 (hoặc 25 nếu phát sóng PAL);
  - đa số 30/60 và nhiều chuyển động nhanh → dựng 30 hoặc 60.
- Nguồn đúng fps dựng: **giữ nguyên từng khung, không nội suy**.
- Nguồn 25 → 24: đổi tốc độ 0,96 (conform) thay vì bỏ khung, nếu không có tiếng đồng bộ quan trọng.
- Nguồn 30/60 → 24: bỏ khung tạo **nhịp không đều** (60→24 là 2:3, 30→24 bỏ 1 trong 5). Lia máy sẽ "khựng nhịp".
  Sửa bằng `cadence_fix.py` (optical flow, đặt mỗi khung ra đúng thời điểm đều).
- Phim 24p bị **đệm lên 30p** (khung lặp 1/5): dùng `decimate` (hoặc `mpdecimate`) để trả về 24p gốc.
- File **VFR** (quay điện thoại, quay màn hình): chuẩn hoá CFR trước khi dựng (`-vf fps=...` hoặc `-fps_mode cfr`).
- Không dùng `minterpolate` cho nguồn VFR/nguồn có khung lặp - kết quả vô hiệu hoặc vỡ hình.

## 1b. Bộ chuyển fps (`scripts/fps_convert.py`) - kết quả đo trên pan chuẩn đều tuyệt đối (10/2026)

| Chuyển đổi | Cách tool chọn | Độ giật sau (0 = đều) | So với bỏ khung thường |
|---|---|---|---|
| 60 → 24 | RIFE lên 96 fps, trộn 2 khung (màn trập 180°), lấy 1/4 | 0,011 | 0,159 (nhịp 2:3, bước ×1,5) |
| 30 → 24 | RIFE lấy mẫu lại đúng thời điểm đều | 0,001 | 0,321 (bước ×1,97) |
| 60 → 30, 120 → 24/30/60, 50 → 25 | lấy 1/k khung, tmix theo góc màn trập | 0,002 | - |
| 60 → 25 | RIFE | 0,039 | - |
| 30 → 60, 30 → 120 | RIFE nội suy | 0,002-0,003 | - |
| 25 ↔ 24, 30 ↔ 29,97 | conform (đổi tốc độ ≤ 4,2 %) | = nguồn | - |
| 120p → 24p slow-mo 5× | phát từng khung, không nội suy | = nguồn | - |

RIFE: `rife-ncnn-vulkan` (MIT, GPU qua Vulkan) ở `~/tools/rife/`; không có thì `--engine flow` (minterpolate).
`probe` phát hiện khung đệm đều đặn (24p trong 30p) **chỉ khi hình đang chuyển động** - cảnh tĩnh/chậm không bị hiểu nhầm.

## 2. Các lỗi và cách phát hiện

| Lỗi | Biểu hiện | Đo bằng | Sửa |
|---|---|---|---|
| Nhịp không đều (cadence) | Lia đều mà thấy giật đều đặn | `probe_qc.py`: tỉ lệ bước chẵn/lẻ > 1,2 hoặc chỉ số giật cao hơn nguồn | `cadence_fix.py`, hoặc dựng ở fps gốc |
| Nguồn giật sẵn | Nguồn đã rung/giật (quay tay, quay màn hình tốc độ thấp, phim cũ re-encode) | chỉ số giật của **chính nguồn** cao | Thay cảnh khác; ổn định hình (`vidstab`) chỉ khi rung tay nhẹ |
| Khung lặp / đứng hình | Hình đứng 1-3 khung rồi chạy tiếp; cuối shot đứng | `probe_qc.py`: dup frames, freeze tail | Lấy dư nguồn, cắt trước đoạn đứng; không kéo dài shot bằng freeze |
| Khung lạc | 1-4 khung của shot bên cạnh lọt vào đầu/cuối | `probe_qc.py`: stray island | Lùi điểm cắt 2-3 khung vào trong ranh giới shot |
| Chớp đen/trắng | 1 khung đen/trắng | `probe_qc.py`: black/white flash | Cắt bỏ, kiểm hiệu ứng nguồn |
| Hiệu ứng nhúng sẵn | Vệt sáng, loá, nhiễu vỡ ô trong nguồn | soát contact sheet | Đổi đoạn nguồn |
| Chạy chậm | Hình bị làm chậm cho đủ thời lượng | so tốc độ với nguồn | Giữ tốc độ thật; lấy thêm cảnh thay vì làm chậm |
| Mờ | Upscale 720p, zoom ảnh quá tay, nén thấp | độ nét (Laplacian var) so với nguồn khác | Nguồn 1080p/4K; CRF 16-18; scale lanczos |

**Chỉ số giật** (judder): trung bình |tốc độ khung - tốc độ trend| / tốc độ trend trên những khung máy đang chuyển động
(optical flow Farneback). Tham chiếu từ một phim doanh nghiệp thực tế: bản gốc trung vị 0,34; bản được khách khen mượt trung vị ~0,15-0,25.
Mục tiêu: **mỗi shot ≤ chỉ số của chính nguồn** và không có shot nào > 0,45 trừ khi nguồn vốn vậy và không có nguồn thay.

## 3. Cắt an toàn trong ranh giới shot

1. Lập danh sách điểm cắt của nguồn (scene detect, ngưỡng `scene > 0.22` trên bản thu nhỏ; hoặc PySceneDetect).
2. Chỉ chọn đoạn nằm trọn trong một shot gốc: vào sau cắt +2 khung, ra trước cắt -3 khung.
3. Sau khi render từng mảnh: soát lại 2 đầu mảnh (thay đổi cứng trong 0,4 s đầu/cuối → kéo điểm cắt vào trong).
4. Mảnh thiếu khung so với kế hoạch → **dồn khung** sang mảnh kề có dư nguồn, không freeze.

## 4. Lia máy mượt hơn

- Ưu tiên shot có tốc độ máy đều; cắt bỏ đoạn tăng/giảm tốc giật cục ở đầu/cuối shot flycam.
- Không tăng tốc nguồn > 1,15× (chuyển động thành giật) - lấy đoạn khác ngắn hơn.
- Motion blur tự nhiên của 24p (màn trập 1/48) làm lia mượt hơn; nguồn màn trập nhanh (1/500) sẽ "lấp lánh" khi lia - chọn tốc độ lia chậm hơn hoặc fps cao hơn.
- Ổn định hình (`vidstabdetect`/`vidstabtransform`, CapCut Stabilize) chỉ cho rung tay nhẹ; crop bù ≤ 5 %.

## 5. Lệnh hay dùng

```bash
# fps, số khung, VFR?
ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate,avg_frame_rate,nb_frames -of csv=p=0 in.mp4
# phim 24p bị đệm 30p -> 24p gốc
ffmpeg -i in.mp4 -vf "fieldmatch,decimate" -r 24 out.mp4      # hoặc: -vf mpdecimate,setpts=N/24/TB -r 24
# CFR hoá file VFR
ffmpeg -i in.mp4 -vf fps=30 -c:v libx264 -crf 16 cfr.mp4
# điểm cắt cảnh
ffmpeg -i in.mp4 -an -vf "scale=320:-1,select='gt(scene,0.22)',showinfo" -f null - 2>&1 | grep pts_time
```
