# ⚡ OmniMedia Pro - Web Tải Nhạc, Video & Tách Nhạc Karaoke AI (Lead/Back Vocal)

Ứng dụng web toàn diện, tốc độ cao giúp:
1. **Tải Video & Audio từ YouTube & Spotify** với chất lượng âm thanh cao nhất: **True 320 kbps (CBR), Lossless FLAC, Master WAV, Opus Native** và Video **MP4 lên đến 4K Ultra HD (60fps)**.
2. **Tách nhạc Karaoke AI (Lead & Backing Vocals)**: Tích hợp công nghệ **MVSep AI (Mô hình BS Roformer SDR: 10.41)** bóc tách bài hát thành **Nhạc nền Beat (Instrumental), Giọng hát chính (Lead Vocals) và Giọng bè (Backing Vocals)**.

---

## 🌟 Tính Năng Chính

### 1. 🎤 Tách Nhạc Karaoke AI (Lead / Back Vocal) - Chuẩn MVSep
- **Công nghệ BS Roformer by MVSep Team (SDR: 10.41)**: Mô hình AI phân tách âm thanh đứng đầu thế giới hiện nay.
- **Tách thành 3 bản thu (Stems) chuyên biệt**:
  * 🎵 **Nhạc nền Beat (Instrumental - Không lời)**: Dùng để hát Karaoke, phối khí, biểu diễn.
  * 🎤 **Giọng hát chính (Lead Vocals)**: Giữ trọn vocal chính rõ nét, không lẫn tạp âm.
  * 🎶 **Giọng bè / Hòa âm (Backing Vocals)**: Bóc tách riêng bè phụ, bè hòa âm.
- **2 Cách nạp nhạc linh hoạt**:
  * **Cách 1**: Kéo thả / Chọn tệp âm thanh trực tiếp từ máy tính (`.mp3`, `.wav`, `.flac`, `.m4a`).
  * **Cách 2**: Dán trực tiếp link YouTube hoặc Spotify -> Tự động tải bản Master 320k về và bóc tách ngay.
- **Trình phát âm thanh (Stem Player) trực quan**: Nghe thử riêng từng phần (Beat, Lead, Bè) ngay trên trang web trước khi tải về, hoặc bấm **Tải toàn bộ (.ZIP)**.
- **Chế độ tách nhanh Offline (FFmpeg 0 giây)**: Cho phép tạo Beat Karaoke ngay lập tức mà không cần kết nối mạng hay API Token.

---

### 2. 🎵 Tách Âm Thanh Chất Lượng Cao Nhất (YouTube & Spotify)
- **MP3 True 320 kbps (Studio Master)**: Bitrate 320 kbps chuẩn CBR, dải tần 20Hz - 20kHz đầy đủ.
- **FLAC Lossless**: Âm thanh bảo toàn 100% dữ liệu phòng thu.
- **Original Audio (Opus / AAC)**: Trích xuất trực tiếp luồng stream gốc cao nhất từ server (Zero Re-encoding).
- **Bộ máy đối soát âm thanh Studio Match Engine**: Khi dán link Spotify, hệ thống tự động đối soát sang kho bản quyền YouTube Music (`filter="songs"`), khớp thời lượng chính xác đến từng 0.1 giây, đảm bảo **100% đúng bản phòng thu gốc của bài hát trên Spotify**, loại bỏ hoàn toàn các bản MV nói chuyện, bản Live tiếng ồn, hay bản Remix.
- **Tự động gắn thẻ ID3 & Ảnh bìa HD**: Tên bài hát, Ca sĩ, Album, Năm phát hành và ảnh bìa 640x640 / 1280x720 được nhúng thẳng vào file.

---

### 3. 🎬 Tải Video YouTube 4K 60fps
- Đầy đủ các độ phân giải: **4K (2160p)**, **2K (1440p)**, **Full HD (1080p)**, **HD (720p)**.
- Tự động gộp video và âm thanh vòm chất lượng cao nhất thành file `.mp4`.

---

## 🚀 Cách Khởi Động & Sử Dụng

### 1. Khởi động Web:
- Bấm đúp vào file **`run.bat`** trong thư mục dự án.
- Mở trình duyệt và truy cập:
  👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)** (hoặc `http://localhost:5000`)

### 2. Sử dụng chức năng Tách Karaoke:
- **Nếu tách từ file có sẵn**: Bấm tab **"Tách Karaoke AI (Lead / Back Vocal)"** ở thanh menu trên cùng -> Kéo thả file nhạc vào ô -> Chọn mô hình *BS Roformer* -> Nhập API Token MVSep (nếu có tài khoản) -> Bấm **"Bắt đầu tách Karaoke"**.
- **Nếu tách từ link YouTube / Spotify**: Dán link vào ô tìm kiếm -> Nhấn **Kiểm tra** -> Ở mục chọn định dạng chọn **"🎤 Tách Karaoke (Lead/Back)"** -> Nhấn nút **Bắt đầu tách**!

---

## 🔑 Hướng Dẫn Lấy MVSep API Token (Miễn phí 100%)
1. Truy cập trang web: **[https://mvsep.com](https://mvsep.com)** và đăng nhập vào tài khoản của bạn (như tài khoản *L6 Lê Quốc Tín*).
2. Bấm vào tên tài khoản ở góc trên bên phải -> Chọn **Settings / Profile**.
3. Sao chép chuỗi **API Token** và dán vào ô **MVSep API Token** trên web app. Hệ thống sẽ tự động lưu nhớ lại vĩnh viễn, bạn chỉ cần nhập một lần duy nhất!
