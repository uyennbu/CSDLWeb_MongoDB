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

### A. Tab 1: CRUD Phim (Collection `movies`)
1. **Read (Đọc & Tìm kiếm):**
   - Tìm kiếm phim theo tiêu đề hoặc lọc theo thể loại (Genre).
   - Tự động hiển thị câu lệnh MongoDB tương ứng:
     `db.movies.find({ ... }).sort({ year: -1 }).limit(12)`
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
