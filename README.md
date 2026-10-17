# Video Studio - dựng phim tự động cho Claude Code

Skill cho Claude Code **tự tạo và tự chỉnh sửa video chuyên nghiệp** bằng một lệnh. Nó dựng phim mới từ storyboard,
lồng tiếng lại video có sẵn bằng giọng tiếng Việt miền Bắc, làm phụ đề, sửa nhịp hình bị giật và kiểm tra chất
lượng trước khi giao. Kiến thức nghề được đúc kết từ các dự án thật: phim doanh nghiệp 10 phút đa ngôn ngữ
và phim giới thiệu dự án hạ tầng 30 giây.

## Làm được gì

| Lệnh | Kết quả |
|---|---|
| `autovideo.py make project.json --out phim_v1.mp4` | Phim hoàn chỉnh từ storyboard. Cảnh video được cắt trong đúng một shot gốc, không lọt khung lạc; ảnh tĩnh có Ken Burns mượt; có chữ trên hình và hoà cảnh. Giọng đọc VieNeu-TTS, nhạc nền tự lặp và tự hạ khi có lời, âm lượng −16 LUFS. Kèm phụ đề burn-in + `.srt` và báo cáo QC |
| `autovideo.py revoice video.mp4 --script loi.txt --voice "Thiện Minh" --out v2.mp4` | Thay giọng thuyết minh. Tách nhạc gốc bằng Demucs, tự dò mốc từng câu trên giọng cũ bằng Whisper, đọc lại bằng giọng mới, đặt đúng mốc, giữ nhạc |
| `autovideo.py subs video.mp4 --script loi.txt --out sub.mp4` | Phụ đề tự động, tự căn mốc theo tiếng của video |
| `autovideo.py qc video.mp4` | Báo cáo: khung lạc, chớp đen/trắng, khung lặp, đứng hình, độ giật từng shot, nhịp khung, LUFS/True Peak |
| `cadence_fix.py` | Sửa lia máy giật nhịp khi đổi 60p/30p sang 24p (optical flow); thử thực tế giảm độ giật 1,03 → 0,57 |
| `--capcut TEN` | Đẩy thêm một bản nháp vào CapCut desktop (qua VectCutAPI) để chỉnh tay |

Kết quả chạy thử (10/2026):
- `revoice` trên video 36 s: tự dò mốc lệch ≤ 0,4 s so với mốc làm tay, lời khớp 97 %, 0 lỗi hình, −16,0 LUFS.
- `make` một bản demo 4 cảnh: 0 lỗi hình, lời khớp 97 %. Tool tự phát hiện điểm cắt có sẵn trong nguồn và rút ngắn cảnh thay vì để hình đứng.

## Kỹ thuật bên trong

- **Khung hình/giây 24 · 25 · 30 · 50 · 60 · 120**, theo cả hai chiều.
  - Đổi 60→24 hoặc 30→24 bằng nội suy RIFE (GPU): độ giật đo được 0,001-0,011, trong khi bỏ khung thông thường là 0,16-0,32.
  - Khi đổi xuống từ nguồn ≥ 2× có motion blur đúng màn trập 180°.
  - Slow-mo thật từ nguồn 120p.
  - Tự phát hiện phim 24p bị đệm thành 30p.
- **Khung hình thông minh**: đổi sang dọc, vuông hoặc 4:5 bằng cách bám mặt người (YuNet), độ nổi bật và chuyển động.
  - Shot tĩnh thì khoá khung như tripod, shot động thì pan mượt có giới hạn tốc độ.
  - Có thêm push/pan/tilt ảo có ease và chống rung vidstab.
- **Kho cảnh**: tách shot, chấm điểm (độ nét, phơi sáng, độ mượt, rung, có người), tìm cảnh theo mô tả bằng CLIP.
- **Màu**: LUT khớp màu giữa các cảnh (Lab), cân tự động, look `clean`/`filmic`/`teal_orange`/`warm`/`cool`/`bw`.
- **Nhạc**: dò phách và tự dời điểm cắt vào phách khi không làm hụt lời.
- **Xuất**: preset YouTube, Facebook, TikTok/Reels/Shorts, vuông, 4:5, trình chiếu, phát sóng EBU R128, ProRes master, HEVC NVENC.
- **Kiến thức điện ảnh**: `references/11` gồm sơ đồ ánh sáng, tỉ lệ tương phản, nhiệt màu, giờ vàng/giờ xanh, tiêu cự, màn trập 180°, ND,
  bố cục 3 lớp, coverage, chuyển động máy, màu, âm thanh, quy tắc dựng của Walter Murch.

## Giọng đọc không bị ép - chọn theo mục đích

- `"giong": "auto"` + `"muc_dich"`: chọn trong 9 mục đích (doanh nghiệp, thời sự, tài liệu, quảng cáo, mạng xã hội, hướng dẫn, sang trọng,
  trẻ em, sự kiện), thêm `"gioi_tinh"`, `"vung"`, `"am_sac"`.
- Điểm chọn giọng dựa trên **hồ sơ đo thật** của từng giọng: tỉ lệ đọc đúng do Whisper nghe lại, cao độ, tốc độ nói.
- Mỗi cảnh hoặc nhân vật có thể dùng giọng riêng. Nguồn giọng gồm: VieNeu (25 giọng), Edge TTS, nhân bản từ mẫu 5-10 s (cần người nói đồng ý), hoặc ghi âm thật.
- `python scripts/voices.py suggest --muc-dich thoi_su --gioi-tinh nu` đưa ra 3-4 lựa chọn kèm lý do.

## Công cụ MCP cho Claude

`scripts/mcp_server.py` biến Video Studio thành 19 công cụ mà Claude gọi trực tiếp, không phải chạy lệnh shell.

- **Công cụ trả kết quả ngay**: probe, QC, contact sheet, gợi ý và danh sách giọng, xem trước phát âm, tìm cảnh, ảnh tĩnh của đồ hoạ.
- **Việc chạy lâu** chạy nền và trả về `job_id`: dựng phim, lồng tiếng, phụ đề, chuyển fps, đổi khung, chống rung, đồ hoạ động, bộ phê bình, mẫu giọng.
  Theo dõi bằng `job_status` / `job_list`; job vẫn giữ trạng thái kể cả khi server khởi động lại.

Đăng ký: `claude mcp add --scope user video-studio -e PYTHONIOENCODING=utf-8 -- python <repo>/scripts/mcp_server.py` (`install.ps1` tự làm).

## Đạo diễn motion và phê bình độc lập

- `scripts/motion_html.py`: đồ hoạ động viết bằng HTML, mỗi khung vẽ từ `seek(t)` và render bằng Playwright, có motion blur sub-frame tự động.
  Có sẵn 2 mẫu: bản đồ tuyến vẽ dần và thẻ chương. Đồ hoạ này đặt được thẳng vào `project.json` như một cảnh.
- `/video:critic`: một agent mới (không tham gia dựng) chấm 8 hạng mục trên thang 10 và làm bài thử xem tắt tiếng.
  Phim được sửa và chấm lại đến khi mọi hạng mục đạt ≥ 8.
  `critic.py` kiểm tra cứng: khung chết, chữ hiện đủ lâu, số liệu có nguồn trong `facts.md`.
- `references/12` gồm:
  - mẫu brief đạo diễn;
  - luật chống "chuyển động kiểu AI";
  - quy trình phim hạ tầng dài: Google Earth Studio, bản đồ 2D, 3D Blender từ DXF, tư liệu hiện trạng, tổ chức ổ đĩa.
- Ý tưởng tham khảo từ [howseen-ai/claude-motion-design](https://github.com/howseen-ai/claude-motion-design) (MIT).

## Độ chính xác

- **Từ điển phát âm** dùng chung (`templates/phat_am.json`) và riêng từng dự án (`"phat_am"`) cho từ viết tắt và tên riêng. Phụ đề vẫn giữ chữ gốc.
- **Nghe lại từng câu**: câu nào khớp dưới `"do_chinh_xac"` (mặc định 97 %) được tự đọc lại, mỗi lần với temperature thấp hơn, rồi giữ bản tốt nhất.
  Báo cáo ghi rõ từng câu.
- **Phụ đề căn theo từng từ** thật trong giọng đã ghép.
- QC tự động: khung lạc, chớp, đoạn đen, đứng hình, độ giật, LUFS.

## Tuỳ chọn dựng

- `"phong_cach"`: `trang_trong`, `dien_anh` (letterbox 2.39, look filmic), `tai_lieu`, `nang_dong` (cắt theo phách), `mang_xa_hoi`.
- Chuyển cảnh từng cảnh: `cut`, `dissolve`, `fade_black`, `dip_white`, `wipe_left/right`, `slide_left/right`, `zoom_in`.
- Khung: `fill`, `fit_blur` (giữ trọn hình, nền mờ), `smart` (bám chủ thể).
- `"nguon": {"tim": "aerial view of a bridge"}` tự lấy cảnh hợp nhất từ kho cảnh.

## Cài đặt (Windows)

Yêu cầu: Python 3.12, ffmpeg có `libass` và `rubberband` (bản gyan.dev full build), GPU NVIDIA nếu muốn Demucs chạy nhanh.

```powershell
git clone https://github.com/viethuynh243/video-studio.git
cd video-studio
powershell -ExecutionPolicy Bypass -File install.ps1
```

`install.ps1` làm 5 việc:
- cài thư viện Python;
- tạo venv riêng cho VieNeu-TTS ở `%USERPROFILE%\tools\venv_vieneu`;
- liên kết `%USERPROFILE%\.claude\skills\video-studio` về repo, để Claude Code nhận skill;
- liên kết `%USERPROFILE%\.claude\commands\video` về thư mục `commands/`, để có các lệnh `/video:*`;
- tải RIFE ncnn-vulkan (nội suy khung bằng GPU) và mô hình YuNet (nhận diện mặt) vào `%USERPROFILE%\tools`.

## Lệnh slash

| Lệnh | Việc |
|---|---|
| `/video:plan [ý tưởng]` | Cùng bàn: 3 hướng sáng tạo, kịch bản, phân cảnh kèm ánh sáng/góc máy/ống kính, kế hoạch quay → project.json |
| `/video:make <kịch bản> <thư mục nguồn>` | Dựng phim mới hoàn chỉnh (hình, giọng, nhạc, phụ đề, QC) |
| `/video:revoice <video> [lời mới] [giọng]` | Lồng tiếng / thay giọng thuyết minh, giữ nhạc gốc |
| `/video:subs <video> [lời] [dịch sang]` | Phụ đề tự động, SRT + burn-in, có thể dịch |
| `/video:reframe <video> [9:16]` | Ngang → dọc/vuông, khung tự bám người nói như người quay thật |
| `/video:library <thư mục>` | Kho cảnh: tách shot, chấm điểm nét/sáng/mượt/rung, tìm cảnh theo mô tả |
| `/video:qc <video> [kịch bản]` | Kiểm tra trước khi giao, bảng Đạt/Chưa đạt kèm số đo |
| `/video:voices [lời mẫu] [lọc]` | Nghe thử và chọn giọng đọc tiếng Việt |
| `/video:fix <video> [mô tả lỗi]` | Sửa giật nhịp, đổi fps 24-120, slow-mo, rung, khung lạc, chớp, lệch tiếng, âm lượng |
| `/video:capcut <video> [tên nháp]` | Tạo bản nháp CapCut desktop để chỉnh tay |

Không cần gõ lệnh cũng được: nói *"lồng tiếng lại video này bằng giọng nam miền Bắc"* thì skill `video-studio` tự chạy.

## Cấu trúc

```
SKILL.md                  bộ não điều hướng cho Claude
commands/*.md             các lệnh /video:*
references/01..10         kiến thức nghề và bài học thực tế
scripts/autovideo.py      cửa chính: make / revoice / subs / qc
scripts/*.py              công cụ thành phần (QC, TTS, mix, phụ đề, Demucs, CapCut, nhịp khung, storyboard)
templates/                project_make.json (dựng mới), storyboard.json
examples/                 demo_make.json, vi_du_loi.txt
```

## Giọng đọc

Dùng [VieNeu-TTS](https://github.com/pnnbao97/VieNeu-TTS) (Apache 2.0, chạy CPU). Có 25 giọng, trong đó nhiều giọng
nam miền Bắc: Thiện Minh (mặc định), Minh Đức (tin tức), Phạm Tuyên, Hải Đăng... Xem đủ bằng `python scripts/tts_vi.py --list`.
Edge-TTS NamMinh bị người nghe nhận là giọng Nam; giọng nam trên CapCut web đọc sai thanh nhiều. Chi tiết ở
`references/05-am-thanh-giong-doc.md`.

## Giấy phép thành phần

Repo này chỉ chứa script và tài liệu. Các mô hình và công cụ được gọi tới có giấy phép riêng:
- VieNeu-TTS: Apache 2.0.
- Demucs: MIT.
- faster-whisper: MIT.
- VectCutAPI: xem repo gốc.
- Mô hình phân loại phương ngữ: xem trang HuggingFace của mô hình.

Phần phim AI ở `references/09` có ghi chú các thành phần chỉ được dùng phi thương mại.
