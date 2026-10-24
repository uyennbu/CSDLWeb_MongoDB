# Hướng Dẫn Nhanh Cụm MongoDB Replica Set (3 Nodes)

## 1. Thông Tin Cụm
- **Replica Set**: `rs0` | **Database**: `shop_online_db` | **Collection**: `products`
- **Nodes**:
  - `mongo1` (Port: `27017`) - **PRIMARY** (priority 2)
  - `mongo2` (Port: `27018`) - **SECONDARY** (priority 1)
  - `mongo3` (Port: `27019`) - **SECONDARY** (priority 1)

---

## 2. Khởi Động & Tự Động Nạp Dữ Liệu
Chạy lệnh tại thư mục `2_cluster`:
```bash
docker compose up -d
```
> Khi 3 node khởi động xong, container `mongo-init` sẽ tự động chạy `demo.js`, kích hoạt Replica Set `rs0` và nạp toàn bộ 10 bản ghi từ `products.json` vào MongoDB.

---

## 3. Kiểm Thử Replication
Chạy script kiểm thử tự động qua Docker:
```bash
docker compose run --rm test-app
```
**Kết quả kiểm tra gồm:**
- Kiểm tra node nào đang là Primary và Secondary.
- Ghi dữ liệu với `WriteConcern(w="majority")`.
- Đọc phân tải từ Secondary bằng `ReadPreference.SECONDARY_PREFERRED`.
- Kiểm chứng trực tiếp (`directConnection`) thấy dữ liệu đã đồng bộ đủ trên cả 3 node.

---

## 4. Truy Cập Thủ Công Qua `mongosh`
Kết nối vào Primary:
```bash
docker exec -it mongo1 mongosh --port 27017
```
Các lệnh thông dụng trong `mongosh`:
```javascript
rs.status()                        // Xem trạng thái cụm
use shop_online_db                // Chuyển sang database
db.products.find()                 // Xem 10 sản phẩm đã nạp
```

---

## 5. Thử Nghiệm Tự Động Bầu Chọn (Failover)
1. **Tắt Primary hiện tại**:
   ```bash
   docker stop mongo1
   ```
2. **Quan sát cụm tự động bầu Primary mới**:
   ```bash
   docker compose run --rm test-app
   ```
   *(Node `mongo2` hoặc `mongo3` sẽ tự động thăng cấp làm PRIMARY).*
3. **Bật lại node cũ**:
   ```bash
   docker start mongo1
   ```
   *(`mongo1` sẽ tái gia nhập, đồng bộ lại dữ liệu và nhận lại quyền PRIMARY).*

---

## 6. Dừng & Dọn Dẹp Cụm
```bash
docker compose down -v
```
