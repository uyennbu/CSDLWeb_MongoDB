# Hướng Dẫn Thiết Lập & Khởi Chạy Web Demo MongoDB (Sample Mflix)

Tài liệu này hợp nhất toàn bộ quy trình từ **chuẩn bị dữ liệu**, **thiết lập cụm MongoDB Replica Set 3 node** đến **cài đặt và vận hành ứng dụng Web UI**.

---

## 1. Tải Dữ Liệu Mẫu `sampledata.archive` Bằng `curl`

Nếu thư mục chưa có sẵn file `sampledata.archive`, bạn có thể tải trực tiếp bộ dữ liệu mẫu chính thức của MongoDB Atlas (dung lượng ~380MB) bằng `curl`:

```bash
cd sample_mflix
curl  https://atlas-education.s3.amazonaws.com/sampledata.archive -o sampledata.archive
```

> [!NOTE]
> File archive này chứa nhiều cơ sở dữ liệu mẫu của Atlas (`sample_mflix`, `sample_airbnb`, `sample_analytics`...). Ở bước nạp dữ liệu bên dưới, tham số `--nsInclude='sample_mflix.*'` sẽ lọc và chỉ import riêng database `sample_mflix`.

---

## 2. Khởi Động Cụm MongoDB Replica Set 3 Node

Cụm gồm 3 node chạy trên Docker:

| Node | Container | Port Host/Container | Vai trò mong muốn |
|---|---|---|---|
| mflix1 | `mflix1` | `27030` | PRIMARY (priority 2) |
| mflix2 | `mflix2` | `27031` | SECONDARY |
| mflix3 | `mflix3` | `27032` | SECONDARY |

> Dùng dải cổng `27030–27032` để không bị xung đột với các cụm MongoDB khác (`27017–27019`). Mọi thao tác quản trị được thực hiện qua `docker exec` mà không cần cài đặt thêm công cụ MongoDB trên máy host.

### Bước 2.1 – Khởi động 3 container
```bash
docker compose up -d
docker compose ps
```
Đảm bảo cả 3 container `mflix1`, `mflix2`, `mflix3` đều ở trạng thái `Up`.

### Bước 2.2 – Khởi tạo Replica Set (chỉ chạy 1 lần)
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
*Đợi khoảng 5–10 giây để cụm hoàn tất bầu chọn PRIMARY.*

### Bước 2.3 – Kiểm tra trạng thái Replica Set
```bash
docker exec mflix1 mongosh --port 27030 --quiet --eval '
rs.status().members.forEach(m => print(m.name, "->", m.stateStr))'
```
Kết quả mong đợi:
```text
mflix1:27030 -> PRIMARY
mflix2:27031 -> SECONDARY
mflix3:27032 -> SECONDARY
```

### Bước 2.4 – Nạp dữ liệu vào Primary
File `sampledata.archive` đã được mount tự động vào container `mflix1` tại `/data/import/sampledata.archive`:

```bash
docker exec mflix1 mongorestore --port 27030 \
  --archive=/data/import/sampledata.archive \
  --nsInclude='sample_mflix.*'
```
*(Lưu ý: Không thêm cờ `--gzip` vì file archive gốc không nén).*

### Bước 2.5 – Kiểm tra dữ liệu đồng bộ
- Kiểm tra số lượng document trên `mflix1` (PRIMARY):
  ```bash
  docker exec mflix1 mongosh --port 27030 --quiet --eval '
  db = db.getSiblingDB("sample_mflix");
  db.getCollectionNames().forEach(c => print(c, db[c].countDocuments()))'
  ```
- Kiểm tra dữ liệu đã tự động replicate sang `mflix2` (SECONDARY):
  ```bash
  docker exec mflix2 mongosh --port 27031 --quiet --eval '
  db.getMongo().setReadPref("secondary");
  print("movies count on secondary:", db.getSiblingDB("sample_mflix").movies.countDocuments())'
  ```

---

## 3. Cài Đặt & Khởi Chạy Ứng Dụng Web UI

### Bước 3.1 – Cài đặt thư viện Python
Yêu cầu Python 3.9+. Cài đặt các phụ thuộc trong [requirements.txt](file:///home/uyenuyen/CSDLWeb_MongoDB/sample_mflix/requirements.txt):

```bash
pip install -r requirements.txt
```

### Bước 3.2 – Chạy ứng dụng Flask
```bash
python3 app.py
```

Mở trình duyệt truy cập:
👉 **http://localhost:5000** (hoặc `http://127.0.0.1:5000`)

> [!TIP]
> **Khả năng tự động chịu lỗi (High Availability):**
> Trong mã nguồn [app.py](file:///home/uyenuyen/CSDLWeb_MongoDB/sample_mflix/app.py), hệ thống đã tích hợp sẵn cơ chế phân giải hostname Docker tự động và Dynamic Proxy kết nối đa tầng. Bạn có thể sử dụng web mà không cần cấu hình file `/etc/hosts`.

---

## 4. Hướng Dẫn Sử Dụng Các Tính Năng Trên Web UI

Giao diện Single Page Application (SPA) được thiết kế tối giản theo phong cách **Beige - White - Light Gray** với 3 tab:

### Tab 1: CRUD & Text Search (Collection `movies`)
- **Full-Text Search (`$text`):** Tận dụng Text Index `MovieFullTextIndex` (`title` trọng số 10, `plot` trọng số 3, `fullplot` trọng số 1). Hệ thống tự động tính điểm liên quan và sắp xếp theo **`textScore`**. Có thể thử các từ khóa: `space war`, `detective`, `godfather`.
- **Regex Search:** Tìm kiếm chuỗi con không phân biệt hoa thường theo tiêu đề phim.
- **Khung Code Tương Ứng:** Hiển thị trực tiếp câu lệnh mongosh thực thi tương ứng với bộ lọc đang chọn.
- **Create / Update / Delete:** Bấm nút **"+ Thêm phim mới"**, **"Sửa"**, hoặc **"Xóa"** trực tiếp trên từng thẻ phim.

### Tab 2: Aggregation Pipeline (Phân Tích Dữ Liệu)
- **Pipeline 1 (`$unwind` + `$group`):** Thống kê số lượng phim và điểm IMDb trung bình/cao nhất theo từng thể loại phim.
- **Pipeline 2 (`$match` + `$sort` + `$group`):** Tìm bộ phim có điểm IMDb cao nhất theo từng năm phát hành.
- Xem trực tiếp pipeline JSON và thời gian thực thi của từng truy vấn.

### Tab 3: Replication Demo & Thử Nghiệm High Availability
- **Giám sát trực quan 3 Node:** Hiển thị thời gian thực vai trò 👑 **PRIMARY**, 🔄 **SECONDARY**, hoặc ❌ **DOWN**, độ trễ ping và số lượng document đã đồng bộ trên từng container.
- **Thử nghiệm Bầu chọn Primary khi có sự cố (Automatic Failover):**
  1. Nhấn nút màu đỏ **"Tắt Container (Dừng Node)"** tại node đang là `PRIMARY`.
  2. Quan sát trong 5–10 giây: 2 node Secondary còn lại tự động tổ chức bầu cử chọn ra một `PRIMARY` mới. Web vẫn truy vấn đọc bình thường mà không bị sập.
  3. Nhấn **"Bật lại Container"**: Node cũ tái gia nhập cụm với vai trò `SECONDARY`, tự động bắt kịp Oplog và giành lại quyền `PRIMARY` nhờ `priority: 2`.

---

## 5. Lệnh Quản Trị Hữu Ích

```bash
# Dừng cụm (giữ nguyên dữ liệu)
docker compose stop

# Khởi động lại cụm
docker compose start

# Xóa toàn bộ container và volumes dữ liệu (làm lại từ đầu)
docker compose down -v
```
