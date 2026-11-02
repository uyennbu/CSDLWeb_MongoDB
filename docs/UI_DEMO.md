# HƯỚNG DẪN AI AGENT: THIẾT KẾ VÀ XÂY DỰNG WEB DEMO MONGODB (SAMPLE MFLIX)

> **Mục đích:** File này là bản đặc tả kỹ thuật toàn diện (Prompt & Specification) để AI Agent tự động sinh ra một ứng dụng Web Demo trực quan, đa tính năng, kết nối trực tiếp với cụm MongoDB Replica Set 3 node.

---

## 1. TỔNG QUAN KIẾN TRÚC DỰ ÁN

- **Dataset:** Dữ liệu mẫu `sample_mflix` (gồm collections `movies`, `comments`, `theaters`, `users`).
- **Hạ tầng cơ sở:** Cụm 3 container Docker MongoDB Replica Set (`mflix1:27030`, `mflix2:27031`, `mflix3:27032`, replSet: `rsMflix`).
- **Backend Stack:** Python Flask (`Flask`, `pymongo`, `bson`).
- **Frontend Stack:** HTML5, CSS3 hiện đại, Vanilla JavaScript (không dùng framework ngoài). Thiết kế theo phong cách tối giản, thanh lịch với bảng màu ấm nhẹ: **Beige (#f9f8f6, #e9e4db), White (#ffffff) và Light Gray (#e5e2db, #f4f1ea)**.
- **Cấu trúc thư mục chuẩn:**
  ```text
  sample_mflix/
  ├── docker-compose.yml       # 3 container MongoDB Replica Set (ports 27030-27032)
  ├── sampledata.archive       # File archive dữ liệu mẫu (tải bằng curl)
  ├── requirements.txt         # Flask, pymongo
  ├── app.py                   # Flask backend + Resilient Connection Proxy
  ├── RUN_WEB.md               # Hướng dẫn thiết lập cluster & chạy ứng dụng web
  ├── templates/
  │   └── index.html           # Single Page Application với 3 Tabs
  └── static/
      ├── style.css            # Giao diện hiện đại, responsive
      └── app.js               # Logic điều khiển, gọi API và render giao diện
  ```

---

## 2. THIẾT KẾ HẠ TẦNG DOCKER & DỮ LIỆU (`docker-compose.yml` & `RUN_WEB.md`)

### 2.1. Tải Dữ liệu Mẫu & Cấu hình `docker-compose.yml`
- **Tải dữ liệu bằng `curl`:** Hướng dẫn tải file `sampledata.archive` chính thức từ MongoDB Atlas S3:
  `curl -L https://atlas-education.s3.amazonaws.com/sampledata.archive -o sampledata.archive`.
- **Cấu hình `docker-compose.yml`:**
  - Tạo 3 services: `mflix1`, `mflix2`, `mflix3`.
  - Dải cổng Host/Container riêng biệt: `27030`, `27031`, `27032` (tránh đụng độ dải cổng `27017..27019`).
  - Lệnh chạy: `mongod --replSet rsMflix --bind_ip_all --port <port>`.
  - Gắn file dữ liệu mẫu vào `mflix1`: `./sampledata.archive:/data/import/sampledata.archive:ro`.
  - Chung mạng `mflix-cluster`, mỗi node có named volume riêng `mflix1_data`, `mflix2_data`, `mflix3_data`.

### 2.2. Trình tự khởi tạo dữ liệu (`RUN_WEB.md`)
1. Khởi động 3 node: `docker compose up -d`.
2. Khởi tạo Replica Set:
   ```bash
   docker exec mflix1 mongosh --port 27030 --eval '
   rs.initiate({
     _id: "rsMflix",
     members: [
       { _id: 0, host: "mflix1:27030", priority: 2 },
       { _id: 1, host: "mflix2:27031" },
       { _id: 2, host: "mflix3:27032" }
     ]
   })'
   ```
3. Nạp dữ liệu:
   ```bash
   docker exec mflix1 mongorestore --port 27030 --archive=/data/import/sampledata.archive --nsInclude='sample_mflix.*'
   ```

---

## 3. THIẾT KẾ BACKEND FLASK KHẢ NĂNG CHỊU LỖI CAO (`app.py`)

Backend cần xử lý tình huống thực tế khi chạy trên máy Host kết nối vào cụm Docker:

### 3.1. Phân giải Hostname & Tự động Failover (Resilient Connection)
- **Patch Hostname:** Do các node bên trong Docker nhận diện nhau bằng `mflix1`, `mflix2`, `mflix3`, backend cần monkey patch `socket.getaddrinfo` để tự động map 3 hostname này về `127.0.0.1` khi chạy ngoài Host (tránh bắt buộc người dùng chỉnh sửa `/etc/hosts`).
- **Connection URI:**
  `mongodb://localhost:27030,localhost:27031,localhost:27032/sample_mflix?replicaSet=rsMflix&readPreference=primaryPreferred`
- **Dynamic Proxy (`DatabaseProxy`, `CollectionProxy`):**
  - Khi node Primary (vd `mflix1`) sập, PyMongo có thể mất vài giây để bầu Primary mới.
  - Proxy bọc biến `db` tự động bắt các lỗi kết nối (`AutoReconnect`, `ServerSelectionTimeoutError`) và lập tức fallback sang đọc trực tiếp (`directConnection=true`) từ một Secondary còn sống (`mflix2` hoặc `mflix3`). Đảm bảo web không bao giờ bị sập hay mất kết nối khi có sự cố.

### 3.2. Chuyển đổi Cú pháp mongosh Trực quan (`to_shell()`)
- Viết hàm `to_shell(value)` chuyển đổi dict/list Python thành chuỗi mongosh thực thụ (vd `{ $text: { $search: "space" }, genres: "Action" }`) để trả về cho Frontend hiển thị người dùng học tập.

### 3.3. Các Endpoints API Cần Xây Dựng
1. **Hệ thống & Trạng thái:**
   - `GET /api/status`: Trả về trạng thái cluster và đếm số lượng tài liệu (`movies`, `comments`, `theaters`, `users`).
2. **Tab 1: CRUD & Text Search:**
   - `GET /api/movies`: Hỗ trợ tìm kiếm phân trang (`q`, `genre`, `mode`, `limit`, `skip`).
     - Khi `mode == "text"`: Dùng `$text: { $search: q }`, chiếu điểm `score: { $meta: "textScore" }`, sort theo `score`.
     - Khi `mode == "regex"`: Tìm chuỗi con không phân biệt hoa thường theo `title`.
     - Trả về câu lệnh `mongo_command` chính xác tương ứng.
   - `GET /api/movies/<id>`: Lấy chi tiết 1 phim.
   - `POST /api/movies`: Thêm phim mới (`insertOne`).
   - `PUT /api/movies/<id>`: Cập nhật thông tin (`updateOne`).
   - `DELETE /api/movies/<id>`: Xóa phim (`deleteOne`).
3. **Tab 2: Aggregation Pipeline:**
   - `GET /api/aggregate/genres-stats`:
     - Pipeline `$unwind: "$genres"` $\rightarrow$ `$group: { _id: "$genres", totalMovies: { $sum: 1 }, avgRating: { $avg: "$imdb.rating" }, maxRating: { $max: { $cond: [{ $isNumber: "$imdb.rating" }, "$imdb.rating", null] } } }` $\rightarrow$ `$match: { totalMovies: { $gte: 50 } }` $\rightarrow$ `$sort` $\rightarrow$ `$limit: 15`.
     - *Lưu ý: Phải dùng `$cond` lọc `$isNumber` cho `maxRating` để tránh chuỗi rỗng `""` chiếm giá trị max theo thứ tự BSON.*
   - `GET /api/aggregate/top-rated-by-year`:
     - Pipeline `$match` lọc rating hợp lệ $\rightarrow$ `$sort: { year: -1, "imdb.rating": -1 }` $\rightarrow$ `$group: { _id: "$year", topMovie: { $first: "$title" }, highestRating: { $first: "$imdb.rating" }, votes: { $first: "$imdb.votes" }, genres: { $first: "$genres" } }` $\rightarrow$ `$sort` $\rightarrow$ `$limit: 20`.
4. **Tab 3: Replication & Failover:**
   - `GET /api/replication/status`: Kết nối vào từng node lấy `rs.status()`, đo `pingMs`, kiểm tra vai trò `PRIMARY`, `SECONDARY` hoặc `DOWN`, và đếm số document thực tế trên từng node.
   - `POST /api/replication/node-action`: Nhận `container` (`mflix1..3`) và `action` (`start`/`stop`), gọi trực tiếp lệnh Docker hệ thống (`docker stop/start <container>`) để phục vụ demo trực quan trên giao diện.

---

## 4. THIẾT KẾ GIAO DIỆN & TƯƠNG TÁC (`index.html`, `style.css`, `app.js`)

### 4.1. Phong cách Thiết kế & Bảng Màu (Color Palette)
Giao diện tuân thủ phong cách **Minimalist & Clean**, mang lại cảm giác trang nhã, không màu mè:
- **Bảng màu chủ đạo (CSS Variables):**
  - `--bg-main: #f9f8f6`: Màu nền trang tổng thể (Light Cream / Warm Beige nhạt).
  - `--bg-card: #ffffff`: Màu nền thẻ, panel, modal (Pure White sạch sẽ).
  - `--border-color: #e5e2db`: Viền phân cách mềm mại (Light Gray / Warm Gray).
  - `--border-focus: #c2bdb4`: Viền khi hover hoặc focus vào input.
  - `--text-main: #2b2927`: Chữ chính (Charcoal đen nhẹ, dễ đọc, không gắt).
  - `--text-muted: #736f69`: Chữ phụ, ghi chú, nhãn thứ cấp (Muted Gray).
  - `--accent-beige: #e9e4db`: Điểm nhấn be ấm, nền phụ.
  - `--accent-dark: #3e3a35`: Màu nút chính, tiêu đề card, tab active.
  - `--badge-bg: #efece6`: Nền badge thể loại, tag.
  - `--code-bg: #f4f1ea`: Nền khối code lệnh MongoDB / JSON pipeline.
  - `--shadow-sm: 0 1px 3px rgba(0,0,0,0.04)` & `--radius: 8px`: Bo góc nhẹ, đổ bóng rất mờ tạo chiều sâu tự nhiên.
- **Typography:** Font hệ thống hiện đại (`-apple-system`, `Segoe UI`, `Roboto`) và font monospace (`Consolas`, `Monaco`) cho các đoạn mã lệnh.

### 4.2. Bố cục Giao diện Single Page
- **Header:** Tên ứng dụng, mô tả và huy hiệu trạng thái cụm Realtime (`status-dot` xanh lá/đỏ, số lượng phim).
- **Navigation Tabs:** 3 nút chuyển đổi mượt mà giữa các mục:
  1. `1. CRUD & Text Search`
  2. `2. Aggregation Pipeline`
  3. `3. Replication`
- **Modal Popup & Toast:** Modal thêm mới/chỉnh sửa phim; Toast thông báo trạng thái thao tác.

### 4.3. Chi tiết 3 Màn hình Tính năng
1. **Tab 1: CRUD & Text Search:**
   - Thanh công cụ tìm kiếm: Ô nhập từ khóa, bộ chọn chế độ (`Full-Text Search` vs `Regex`), dropdown danh sách `Thể loại` (distinct genres), nút "+ Thêm phim mới".
   - **Khung câu lệnh tạo Text Index:** Một thẻ `<details>` có thể thu gọn, chỉ hiển thị khi chọn chế độ Full-Text Search, in câu lệnh index chuẩn được áp dụng:
     ```javascript
     db.movies.createIndex(
       { title: "text", plot: "text", fullplot: "text" },
       { weights: { title: 10, plot: 3, fullplot: 1 }, name: "MovieFullTextIndex", default_language: "english" }
     );
     ```
   - **Khung Code Query động (`.code-box`):** Hiển thị trực tiếp câu lệnh `find(...)` kèm projection và `.sort({ score: { $meta: 'textScore' } })` đồng bộ 100% với backend.
   - **Lưới hiển thị phim (Movie Grid):** Thẻ phim hiển thị Poster/Tiêu đề, năm, điểm IMDb, badge `🎯 TextScore: X.XX` (nếu tìm text search), danh sách thể loại, tóm tắt và 2 nút "Sửa (Update)" / "Xóa (Delete)".
2. **Tab 2: Aggregation Pipeline:**
   - Các nút kích hoạt kịch bản phân tích (`$unwind + $group`, `$match + $sort + $group`).
   - Khung code hiển thị toàn bộ mảng Pipeline JSON đang thực thi.
   - Bảng kết quả dữ liệu (`data-table`) hiển thị thời gian chạy (`X.XXs`), định dạng icon đẹp mắt (⭐, số lượng phim).
3. **Tab 3: Replication Demo (High Availability):**
   - Lưới 3 thẻ đại diện cho 3 node `mflix1`, `mflix2`, `mflix3`.
   - Mỗi thẻ hiển thị: Host Port, tên Container, Badge trạng thái (👑 **PRIMARY**, 🔄 **SECONDARY**, ❌ **DOWN**), độ trễ ping (`ms`), số lượng document đã đồng bộ.
   - Nút tương tác: **"Tắt Container (Dừng Node)"** (màu đỏ) và **"Bật lại Container"** (màu xanh).
   - Phần hướng dẫn thử nghiệm: Hướng dẫn người dùng bấm tắt node Primary $\rightarrow$ quan sát 2 node còn lại tự động tổ chức bầu cử chọn Primary mới trong 5-10 giây mà web vẫn truy vấn bình thường.

---

## 5. NGUYÊN TẮC THỰC THI CHO AI AGENT
1. **Độc lập và tự khép kín:** Mã nguồn tạo ra phải chạy được ngay sau khi `docker compose up -d` và `pip install -r requirements.txt`.
2. **Xử lý dữ liệu sạch:** Dữ liệu MongoDB sample đôi khi có các trường bị lỗi định dạng (ví dụ năm dạng `2010è` hoặc rating dạng chuỗi rỗng `""`), backend cần hàm làm sạch trước khi trả về Frontend để tránh lỗi render.
3. **Trải nghiệm trực quan:** Mọi thao tác truy vấn đều phải sinh ra câu lệnh shell MongoDB tương ứng để người dùng vừa trải nghiệm vừa học cú pháp lệnh.
