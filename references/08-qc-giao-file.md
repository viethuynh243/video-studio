# 08 - QC và giao file (bắt buộc trước mỗi lần gửi)

## 1. Chạy máy

```bash
S=~/.claude/skills/dung-phim-chuyen-nghiep/scripts
python $S/probe_qc.py BAN_DUNG.mp4 --json rev/qc.json        # khung lạc, chớp, khung lặp, giật, LUFS, viền
python $S/contact_sheet.py BAN_DUNG.mp4 rev/sheet.jpg         # soát mắt từng shot
python $S/speech_check.py rev/voice.wav --ref script.txt     # lời khớp kịch bản (rãnh giọng riêng)
```

Ngưỡng đạt:

| Hạng mục | Đạt |
|---|---|
| Khung lạc (đảo 1-4 khung giữa hai cắt) | 0 |
| Chớp đen/trắng 1 khung | 0 (trừ hiệu ứng có chủ ý) |
| Khung lặp / đứng hình trong shot chuyển động | 0 |
| Chỉ số giật từng shot | ≤ chỉ số của nguồn đó; trung vị phim ≤ 0,3 |
| Shot dài | ≤ 8 s (trừ logo đầu/cuối) |
| Loudness | đúng mục tiêu ±0,5 LU; True Peak ≤ -1 dBTP |
| Lời | khớp kịch bản ≥ 97 % trên rãnh giọng (lỗi còn lại phải giải thích được) |
| Phụ đề | khớp văn bản duyệt 100 %; không có "—"; ≤ 2 dòng; ≤ 17 ký tự/s |
| Thời lượng/số khung | `nb_frames = fps × duration` |

## 2. Soát mắt (contact sheet)

Với mỗi shot nhìn 3 khung (đầu/giữa/cuối), hỏi:
- Đúng công trình/sự kiện được đọc? Đúng đơn vị (không lấy công trình của đơn vị khác)?
- Có logo lạ, QR, quảng cáo, khẩu hiệu, chữ "Tư liệu", watermark, người không được phép?
- Có lặp cảnh/lặp địa điểm cùng góc?
- Phụ đề có chạm chữ trên hình?
- Ảnh mờ, vỡ, sai màu?

## 3. Bảng kiểm góp ý

Mở `rev/GOP_Y_DA_NHAN.md`, ghi kết quả từng dòng (Đạt/Chưa + bằng chứng). Chưa đạt thì chưa gửi.

## 4. Gửi

- File > 30 MB không gửi qua điện thoại được: kèm bản nháp 720p CRF 23 nếu người dùng đang xem từ xa.
- Báo cáo theo mẫu ở `01-quy-trinh.md` mục 4.
- Chỉ thay bản chính khi người dùng duyệt (luật bất biến 1).
