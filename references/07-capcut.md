# 07 - Lái CapCut: MCP, VectCutAPI, CapCut web

## 1. Ba đường vào CapCut

| Đường | Dùng cho | Hạn chế |
|---|---|---|
| **VectCutAPI HTTP** (`~/tools/VectCutAPI`, Flask `localhost:9001`) | Tạo/sửa bản nháp CapCut desktop: video, âm thanh, chữ, phụ đề, ảnh, keyframe, hiệu ứng, sticker | Không có TTS; không render ra mp4 (người dùng bấm Export trong CapCut) |
| **MCP `capcut`** (`mcp__capcut__capcut_*`) | Bọc lại VectCutAPI cho gọi trực tiếp | `capcut_create_draft` từng lỗi → gọi HTTP thẳng bằng `scripts/capcut_api.py` |
| **CapCut web** (capcut.com, Chrome của người dùng đã đăng nhập) | TTS 12 giọng Việt, công cụ AI | Chập chờn, tốn credit; xem mục 4 |

Bản nháp desktop nằm ở `%LOCALAPPDATA%/CapCut/User Data/Projects/com.lveditor.draft/<tên>`.
Kiểm server: `curl -X POST localhost:9001/list_projects`. Server chưa chạy → `python capcut_server.py` trong thư mục VectCutAPI (chạy nền).

## 2. Endpoint chính (POST JSON)

| Endpoint | Tham số quan trọng |
|---|---|
| `/create_draft` | `width`, `height` → trả `draft_id` |
| `/add_video` | `draft_id`, `video_url` (đường dẫn file cục bộ được), `start`, `end` (trong nguồn), `target_start` (trên timeline), `speed`, `volume`, `track_name`, `transition`, `transition_duration`, `scale_x/y`, `transform_x/y`, mask |
| `/add_audio` | `draft_id`, `audio_url`, `start`, `end`, `target_start`, `volume`, `speed`, `track_name`, `effect_type` |
| `/add_text` | `text`, `start`, `end`, `font`, `font_color`, `font_size`, `transform_x/y`, `track_name`, `bold`, `alignment`, intro/outro animation |
| `/add_subtitle` | `srt` (nội dung hoặc đường dẫn), `font`, `font_size`, `font_color`, `border_*`, `background_*`, `transform_y` (mặc định -0,8) |
| `/add_image`, `/add_video_keyframe`, `/add_effect`, `/add_sticker` | xem `capcut_server.py` |
| `/save_draft` | `draft_id`, `draft_folder` (thư mục `com.lveditor.draft`), `project_name` |
| `/list_projects`, `/read_project`, `/get_duration` | đọc trạng thái |
| `/get_transition_types`, `/get_font_types`, `/get_intro_animation_types`, `/get_audio_effect_types`... (GET) | liệt kê tên hợp lệ |

Đơn vị thời gian: giây. Toạ độ `transform_x/y` theo tỉ lệ khung (-1..1), `y=-0.8` là gần đáy.

## 3. Quy trình đẩy một bản dựng vào CapCut

1. Dựng và kiểm mọi thứ bằng ffmpeg trước (CapCut chỉ là nơi người dùng tinh chỉnh/xuất).
2. Tạo nháp mới với tên có phiên bản (không ghi đè nháp cũ): `capcut_api.py build --spec draft.json`.
3. Track gợi ý: `video_main` (hình không tiếng), `voice` (giọng), `music` (nhạc đã duck hoặc nhạc gốc + keyframe âm lượng), `sub` (phụ đề SRT).
4. Lưu, mở CapCut desktop kiểm nháp hiện đúng, rồi báo người dùng tên nháp.
   `save_draft` tạo thư mục mang tên nháp và thêm một bản làm việc `dfd_cat_<id>`; `list_projects` có thể chỉ hiện `dfd_cat_*` - kiểm thư mục tên nháp trên đĩa.

## 4. CapCut web: bài học khi tự lái (Claude in Chrome)

- Cần người dùng **đã đăng nhập** trong Chrome của họ; không nhập mật khẩu thay.
- Mỗi lần Generate tốn ~1 credit / ≤ 300 ký tự; hộp "Credits will be consumed" phải bấm xác nhận.
- Bấm vào thẻ giọng đang chọn **sẽ bỏ chọn** - kiểm class `toneItem--selected` trước khi bấm Generate.
- Ô nhập là contenteditable: dùng thao tác gõ thật (`computer type`) sau khi click vào ô; `execCommand` chọn-hết hay làm nát chữ.
- Panel Results hay treo "Generating 99%" nhưng file đã có trong **History**.
- Nút Download/URL trong Results trả **M4A mã hoá CENC** (không phát được). Bản phát được là MP3 mà trình phát History
  nạp khi bấm Play - bắt bằng hook `HTMLMediaElement.prototype.src`.
- CSP chặn `fetch` ra `localhost`; Chrome chặn tải nhiều file tự động. Cách đưa file về: tạo nút phủ toàn trang, người
  dùng (hoặc click thật) bấm → `window.open('http://127.0.0.1:8765/')` (trang nhận cục bộ) → `postMessage` bytes → trang nhận POST lưu đĩa.
- Cửa sổ Chrome bị thu nhỏ/che thì screenshot timeout và click không ăn - phóng to lại cửa sổ.
- Kết luận: CapCut web chỉ dùng khi cần đúng giọng của CapCut; mặc định dùng VieNeu-TTS cục bộ (ổn định, miễn phí, nhiều giọng Bắc hơn).
