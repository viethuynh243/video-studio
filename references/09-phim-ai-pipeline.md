# 09 - Phim AI / micro-drama: storyboard JSON → ảnh → video → lời → lip-sync → hàng đợi

Phần này chưng cất từ một thread Threads (10/2026) quảng bá quy trình "micro-drama AI chi phí 0đ", đối chiếu với thực tế
kỹ thuật và pháp lý. Lấy phần đúng, bỏ phần thổi phồng.

## 1. Bốn bước trong thread và đánh giá

| Bước (thread) | Phần đúng, nên làm | Phần thổi phồng / thiếu |
|---|---|---|
| 1. "Băm kịch bản thành JSON" - mỗi cảnh có góc máy, bối cảnh, hành động, thoại, cảm xúc | **Đúng và quan trọng nhất.** Storyboard có cấu trúc thì máy tự sinh prompt, tự xếp hàng đợi, tự kiểm. Dùng `templates/storyboard.json` + `scripts/storyboard.py` | JSON không thay được biên kịch giỏi; cần thêm trường `seed`, `ref_nhan_vat`, `thoi_luong`, `chuyen_canh`, `trang_thai` để tái lập |
| 2. "Khoá khuôn mặt + ép form": ComfyUI local + IPAdapter FaceID + ControlNet (Depth/Canny/OpenPose) | Đúng hướng: ảnh tham chiếu nhân vật cố định, ControlNet giữ dáng/bố cục, seed cố định | FaceID **không khoá chết** - vẫn trôi mặt qua góc/ánh sáng; cần thêm LoRA nhân vật huấn luyện riêng và soát bằng điểm giống mặt. Model InsightFace (buffalo_l/antelopev2) **giấy phép phi thương mại**. Repo `ComfyUI_IPAdapter_plus` (cubiq) đã ngừng phát triển tích cực - kiểm tương thích phiên bản ComfyUI |
| 3. "Chuyển động vi mô & lip-sync": khoá máy tĩnh, chỉ cho cơ mặt chuyển động; thoại qua TTS rồi lip-sync | **Rất thực dụng**: video AI còn yếu ở hành động phức tạp, cảnh máy tĩnh + chuyển động nhỏ cho tỉ lệ dùng được cao nhất | "Độ trễ bằng không, khớp từng âm tiết" là quảng cáo. Lip-sync mở (LatentSync - Apache 2.0, MuseTalk) tốt ở mặt chính diện, kém khi nghiêng/che miệng; Wav2Lip **không dùng thương mại** |
| 4. "Task queue cày đêm, chi phí 0đ" | Đúng: tự động hoá bằng hàng đợi (ComfyUI `/prompt` API, script Python), chạy qua đêm, có retry/log | "0đ" sai: tiền GPU (VRAM 12-24 GB+), điện, thời gian soát lỗi. Phần lớn chi phí thật là **người soát và chọn lại** cảnh hỏng |

Phần còn lại của thread (tuyển người, "chia %", "húp tiền Tây") là tuyển dụng/marketing - không phải kỹ thuật; cẩn trọng với lời hứa thu nhập.

## 2. Quy trình đề xuất (chạy được trên máy có GPU NVIDIA)

1. **Kịch bản → storyboard JSON** (`templates/storyboard.json`): mỗi `canh` có `id`, `thoi_luong`, `co_canh`, `goc_may`,
   `chuyen_dong` (mặc định `static`), `boi_canh`, `nhan_vat` (id → ảnh tham chiếu), `hanh_dong` (một hành động nhỏ),
   `thoai` + `giong`, `cam_xuc`, `prompt_bo_sung`, `seed`.
2. **Bible nhân vật/bối cảnh**: mỗi nhân vật 1 bộ 5-10 ảnh tham chiếu sạch (chính diện, 3/4, nghiêng), trang phục cố định;
   có quyền sử dụng khuôn mặt (người thật phải đồng ý bằng văn bản).
3. **Ảnh khoá khung (keyframe)**: ComfyUI (SDXL/Flux) + IPAdapter/PuLID/LoRA nhân vật + ControlNet theo bố cục. Sinh 4 biến thể/cảnh, chọn 1.
4. **Ảnh → video**: Wan 2.x I2V / LTX-Video / HunyuanVideo (mở, chạy cục bộ), clip 3-5 s, máy tĩnh hoặc push-in nhẹ.
5. **Thoại**: `tts_vi.py` (VieNeu, giọng theo nhân vật, cố định cho cả series).
6. **Lip-sync**: LatentSync/MuseTalk trên clip có mặt chính diện; cảnh nghiêng thì cho thoại thành lời dẫn (off) thay vì ép khớp môi.
7. **Dựng**: ghép theo storyboard, nhạc, SFX, phụ đề, QC như phim thường (`08-qc-giao-file.md`).
8. **Hàng đợi**: `storyboard.py jobs` sinh danh sách job JSON; một worker gửi vào ComfyUI API:
   - `POST http://127.0.0.1:8188/prompt` body `{"prompt": <workflow dạng API>, "client_id": "..."}` → `prompt_id`
   - theo dõi `GET /history/<prompt_id>` (hoặc websocket `/ws?clientId=...`), lấy file qua `/view?filename=...`
   - ghi trạng thái từng job vào JSON (chờ/đang chạy/xong/lỗi), retry tối đa 2 lần, seed mới khi lỗi.

## 3. Kiểm chất lượng riêng cho phim AI

- Giống mặt: so embedding khuôn mặt từng clip với ảnh tham chiếu; dưới ngưỡng → sinh lại.
- Tay/chân lỗi, chữ rác trong hình, vật thể biến dạng giữa clip: soát contact sheet từng clip.
- Nhấp nháy (flicker) và trôi màu giữa các clip của cùng cảnh.
- Lip-sync lệch > 2 khung: sửa hoặc chuyển thành thoại off.

## 4. Pháp lý và nền tảng

- Không dùng mặt/giọng người thật khi chưa có đồng ý. Không nhân bản giọng người nổi tiếng/phát thanh viên.
- YouTube, TikTok, Facebook yêu cầu **gắn nhãn nội dung AI** khi hình người/sự kiện trông như thật.
- Kiểm giấy phép từng mô hình trước khi làm việc thương mại (nhiều checkpoint/thành phần là phi thương mại).
