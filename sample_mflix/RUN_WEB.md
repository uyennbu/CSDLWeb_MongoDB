# Hướng Dẫn Chạy Web UI Demo MongoDB (Sample Mflix)

Web UI demo các truy vấn cơ bản **CRUD** và **Aggregation Pipeline** trên cơ sở dữ liệu `sample_mflix` (MongoDB Replica Set 3 node).

Giao diện thiết kế theo phong cách tối giản, tinh tế với bảng màu **White - Beige - Light Gray**.

---

## 1. Cài đặt thư viện cần thiết

Các thư viện đã được liệt kê trong [requirements.txt](file:///home/uyenuyen/CSDLWeb_MongoDB/sample_mflix/requirements.txt):

```bash
cd sample_mflix
pip install -r requirements.txt
```

> **Danh sách gói cài đặt:**
> - `Flask>=3.0.0`: Web framework nhẹ nhàng, dễ triển khai.
> - `pymongo>=4.6.0`: MongoDB Driver chính thức cho Python.
> - `python-dotenv>=1.0.0`: Quản lý biến môi trường.

---

## 2. Khởi động MongoDB Cluster

Nếu cluster chưa chạy, khởi động bằng Docker Compose:

```bash
docker compose up -d
```

Kiểm tra 3 container đang chạy bình thường (`mflix1`, `mflix2`, `mflix3`):
```bash
docker compose ps
```

---

## 3. Khởi chạy Web Server

Chạy ứng dụng Flask:

```bash
python3 app.py
```

Truy cập vào trình duyệt web tại địa chỉ:
👉 **http://localhost:5000** hoặc **http://127.0.0.1:5000**

---

## 4. Các tính năng chính trên Web UI

### A. Tab 1: CRUD Phim & Text Search (Collection `movies`)
1. **Read & Full-Text Search:**
   - **Chế độ 1: 🔍 MongoDB Full-Text Search (`$text`)**: 
     - Tận dụng Text Index có sẵn (`cast`, `fullplot`, `genres`, `title`).
     - Tự động tính điểm liên quan và sắp xếp theo **`textScore`** (`score: { $meta: "textScore" }`).
     - Có thể thử từ khóa: `"space war"`, `"detective murder"`, `"godfather mafia"`.
     - Câu lệnh MongoDB:
       ```javascript
       db.movies.find(
         { $text: { $search: "space war" } },
         { title: 1, year: 1, score: { $meta: "textScore" } }
       ).sort({ score: { $meta: "textScore" } }).limit(12)
       ```
   - **Chế độ 2: 🔤 Regex thông thường**:
     - Tìm kiếm chuỗi con không phân biệt hoa thường theo tiêu đề (`title: { $regex: ..., $options: "i" }`).
   - Tự động hiển thị câu lệnh MongoDB tương ứng trực tiếp trên giao diện.
2. **Create (Thêm mới):**
   - Bấm nút **"+ Thêm phim mới (Create)"** ở góc trên.
   - Nhập tên phim, năm, điểm IMDb, thể loại và tóm tắt.
   - Thực thi lệnh: `db.movies.insertOne({ ... })`.
3. **Update (Chỉnh sửa):**
   - Bấm **"Sửa (Update)"** ở thẻ phim bất kỳ.
   - Chỉnh sửa thông tin và lưu lại.
   - Thực thi lệnh: `db.movies.updateOne({ _id: ... }, { $set: { ... } })`.
4. **Delete (Xoá):**
   - Bấm **"Xóa (Delete)"** trên thẻ phim (có hộp thoại xác nhận).
   - Thực thi lệnh: `db.movies.deleteOne({ _id: ... })`.

---

### B. Tab 2: Aggregation Pipeline (Phân tích dữ liệu)
Cung cấp 3 kịch bản minh họa pipeline thực tế kèm câu lệnh code mẫu:

1. **Pipeline 1: `$unwind` + `$group`**
   - Bóc tách mảng `genres` và gom nhóm tính tổng số phim cùng điểm IMDb trung bình của từng thể loại.
2. **Pipeline 2: `$match` + `$sort` + `$group`**
   - Tìm bộ phim có điểm IMDb cao nhất trong mỗi năm (lấy `$first` sau khi sắp xếp).
3. **Pipeline 3: `$lookup` (JOIN Collections)**
   - Nối bảng `movies` với `comments` theo `movie_id` để thống kê các phim có nhiều bình luận tương tác nhất.

---

### C. Tab 3: Replica Set & High Availability (Replication Demo)
Trang chuyên biệt để trực quan hóa cụm 3 node MongoDB (`rsMflix`):

1. **Giám sát trực tiếp trạng thái 3 Node:**
   - Hiển thị vai trò hiện tại của từng container: 👑 **PRIMARY**, 🔄 **SECONDARY**, hoặc ❌ **DOWN**.
   - Xem độ trễ ping (`ms`), cổng kết nối và số lượng documents đồng bộ trên từng node.
2. **Demo Đồng bộ dữ liệu (Replication Sync Test):**
   - Bấm nút **"Thực hiện kiểm tra đồng bộ (Sync Test)"**: Hệ thống ghi một bản ghi mới vào Primary rồi ngay lập tức đọc trực tiếp từ từng Secondary để kiểm chứng dữ liệu đã được nhân bản sang tất cả các node.
3. **Demo Tự phục hồi & Bầu cử lại (Automatic Failover):**
   - Bấm **"🛑 Tắt Container (Giả lập chết)"** ngay tại node Primary.
   - Quan sát 2 node Secondary còn lại tự động tổ chức bầu cử chọn ra một **PRIMARY mới** mà không làm gián đoạn cụm.
   - Bấm **"▶️ Bật lại Container"**: Node bị tắt sẽ khởi động lại và tự gia nhập cụm với vai trò Secondary, đồng bộ lại oplog từ Primary mới.

---

### D. Tab 4: Sharding & Scale-Out (Phân mảnh ngang dữ liệu)
Trang trực quan hóa toàn diện kiến trúc **Sharded Cluster**:

1. **Sơ đồ cấu trúc 3 lớp:**
   - **Client / Web App** $\rightarrow$ **mongos (Router)** $\rightarrow$ **Config Server (`cfgRS`)** $\rightarrow$ **3 Shards (`shard1RS`, `shard2RS`, `shard3RS`)**.
2. **Phân bổ Shard theo Shard Key (`year`):**
   - **Shard 1 (`shard1RS`):** `year < 1980` (Phim cổ điển) $\approx$ 18% dữ liệu.
   - **Shard 2 (`shard2RS`):** `1980 <= year < 2000` (Thời kỳ hoàng kim) $\approx$ 27% dữ liệu.
   - **Shard 3 (`shard3RS`):** `year >= 2000` (Điện ảnh hiện đại) $\approx$ 55% dữ liệu.
3. **Demo 1: So sánh Định tuyến mongos Router:**
   - **Targeted Query (Đơn Shard):** Khi truy vấn có Shard Key (`{ year: 1995 }`), `mongos` tra cứu Config Server và gửi thẳng truy vấn tới **DUY NHẤT 1 Shard** (`shard2RS`) $\rightarrow$ Cực nhanh và tối ưu tài nguyên.
   - **Targeted Range Query (Đa Shard):** Khi truy vấn khoảng (`{ year: { $gte: 1975, $lte: 1985 } }`), `mongos` chỉ gửi tới **2 Shard liên quan** (`shard1RS`, `shard2RS`).
   - **Scatter-Gather Query (Phát tán toàn cụm):** Khi truy vấn KHÔNG có Shard Key (`{ genres: "Action" }`), `mongos` buộc phải gửi đến **TẤT CẢ các Shard** rồi gom kết quả $\rightarrow$ Tốn tài nguyên mạng và CPU.
4. **Demo 2: Định tuyến tự động khi Ghi (Insert Routing):**
   - Thử nhập năm phát hành để xem `mongos` tự động tính toán phân bổ bản ghi mới vào đúng Shard lưu trữ theo Range Partitioning.
