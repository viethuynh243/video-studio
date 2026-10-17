# 10 - Bài học thực tế (đừng lặp lại)

Rút từ hai dự án thật: một phim doanh nghiệp 10 phút (bản tiếng nước ngoài + phụ đề, 8 vòng sửa) và một phim giới thiệu dự án hạ tầng 30 s (thay giọng đọc).

## Hình
1. **"Mượt" phải đo, không đoán.** Hai lần gửi bản "đã mượt" bị trả về vì chỉ số cũ không bắt được nguồn vốn đã giật
   và nhịp 2:3 sau khi đổi 60p→24p. Phải đo từng shot, so với chính nguồn.
2. Bản gốc dựng 24p mượt hơn bản dựng 30p từ cùng nguồn → **dựng ở fps của nguồn chính**, không mặc định 30.
3. Optical flow retime: dấu của véc-tơ warp từng sai (`gx - frac*flow` mới đúng). Luôn xuất thử 1 shot, xem từng khung.
4. Khung lạc ở điểm cắt đến từ việc tin danh sách cắt cảnh tự động; cần danh mục ranh giới shot + kiểm hai đầu mảnh sau render.
5. Không làm chậm hình để đủ thời lượng - khách thấy "chạy chậm, lê thê". Lấy thêm cảnh.
6. Shot phẳng dài (cầu dài, 10 s) bị chê; ≤ 7-8 s và chọn cảnh hiện đại, đẹp.
7. Phim cũ (nguồn lưu trữ): không kéo dài ra ngoài đoạn đã chọn, không "refine" tự động - hay dính hiệu ứng nhúng sẵn.

## Nội dung
8. Mở đầu phải là công trình chủ lực của khách; một lần lấy nhầm cảnh công trình do đơn vị khác thực hiện đã bị bắt lỗi ngay.
9. Chỉ một khung hình 0,4 s chứa công trình của đơn vị khác cũng bị coi là sai thông tin.
10. Người không còn được phép xuất hiện, chữ "Tư liệu" in sẵn, banner, QR, vệt sáng kỹ thuật số: soát contact sheet từng shot.
11. Tần suất sự kiện phải khớp hình (giải thưởng 2 năm/lần vs ngày hội hằng quý).

## Lời, chữ
12. Gạch dài "—" trong phụ đề bị đọc như dấu gạch chéo; gạch nối trong chữ đưa vào TTS bị đọc thành "đến".
13. Bản dịch: khách yêu cầu đúng 100 % nghĩa và ngữ cảnh; ghi rõ câu còn phân vân để khách quyết.
14. Chữ dịch chèn trên slide phải mờ, chỉ để ở chỗ có số liệu; chỗ nào lời đã nói rõ thì bỏ.

## Âm thanh
15. Đổi tempo nhạc để khớp thời lượng → khách nghe "nhạc chạy nhanh". Giữ tốc độ gốc, nối/cắt nhạc ở phách.
16. "Giọng Bắc" là yêu cầu cứng. NamMinh (Edge) bị nghe là giọng Nam; giọng CapCut tên "Duy Bắc" đọc sai thanh.
    VieNeu-TTS cho giọng nam Bắc đạt (giọng được duyệt: Thiện Minh). Luôn cho nghe nhiều giọng và lưu lại tất cả.
17. Whisper trên bản trộn "bịa" chữ ở đoạn chỉ có nhạc → kiểm lời trên rãnh giọng riêng.

## Vận hành
18. Hai render song song dùng chung cache → lỗi khoá file. Một lượt một lúc.
19. Demucs CLI lỗi thiếu module → gọi bằng Python API.
20. MCP CapCut `create_draft` lỗi → gọi VectCutAPI HTTP trực tiếp.
21. Thay bản chính chỉ sau khi duyệt; giữ bản lưu; không xoá file.

## Tự động hoá (nâng cấp 10/2026)
22. QC phải biết chuyển cảnh đã lên kế hoạch (dip trắng, slide, fade đen, thẻ nền tối): nếu không, mỗi khung chuyển cảnh bị báo "khung lạc".
    `make` ghi `_plan.json`; `probe_qc`/`critic.py` tách riêng các thay đổi nằm trong đó.
23. Kiểm lời bằng Whisper phải so với **cả** chữ gốc và cách đọc (từ điển phát âm). ASR viết "BIM", "1.200m", "UBND" theo kiểu của nó;
    so một phía sẽ báo sai và bắt đọc lại vô ích. Chuẩn hoá số (dấu nghìn) và tách số khỏi đơn vị.
24. Đọc lại tự động sửa được lỗi thanh ngẫu nhiên nhưng không sửa được giọng đọc sai cố định (vd "tỉnh" thành "tình" ở một giọng).
    Khi còn dưới ngưỡng sau 3 lần, báo người nghe lại, hoặc đổi cách viết câu, hoặc đổi giọng.
25. Tự chọn cảnh bằng CLIP với độ khớp < 0,25 hay sai nội dung (đã gặp chọn nhầm slide đồ hoạ cho "hội trường").
    Luôn cảnh báo và xem contact sheet.
26. Ngưỡng "khung chết": hình đứng thật có chênh lệch ≈ 0-0,02; trôi chậm/zoom chậm ≈ 0,1. Dùng 0,04, nếu không sẽ phạt nhầm các cảnh trôi nhẹ có chủ ý.
27. Thẻ màu và đồ hoạ phải có chuyển động vi mô đến khung cuối (ánh sáng trôi, zoom liên tục). Easing dừng hẳn ở cuối tạo khung chết.
28. Sửa file bằng heredoc trong bash dễ làm hỏng chuỗi `\1`, `\d` (thành ký tự điều khiển). Viết script vá ra file rồi chạy, sau đó quét ký tự điều khiển (`grep -P "[\x01-\x08]"`).
29. Đối chiếu số với nguồn bằng sai số tương đối (0,5 %) cho qua cả năm bịa (2010 khớp 2000). Chỉ nhận số làm tròn theo số chữ số có nghĩa,
    năm không bao giờ được làm tròn; số chỉ khớp qua một phép suy thì hiện kèm phép suy để người xác nhận.
30. Người duyệt mù chỉ nhận các mục bị gắn cờ, nên mỗi mục phải mang theo **câu đầy đủ và vị trí** của nó. Có lần cờ "phép tính sai"
    thiếu câu, người duyệt không sửa được. Bản sửa của người duyệt có thể thêm lỗi mới (vd. một năm không nguồn): luôn chạy `compare` trước khi nhận.
