# HƯỚNG DẪN AI AGENT: TRIỂN KHAI MONGODB REPLICATION (REPLICA SET 3 NODE)

> **Mục đích:** Prompt chuẩn để AI Agent tự động code 2 file: `docker-compose.yml` và `HUONG_DAN_REPLICATION.md` cho bài thực hành MongoDB Replication.

---

## 1. YÊU CẦU FILE `docker-compose.yml`

- **3 Services:** `mongo1`, `mongo2`, `mongo3` (dùng image `mongo:latest`, chung network `mongo-cluster`).
- **Command:** `["mongod", "--replSet", "rs0", "--bind_ip_all", "--port", "<cổng>"]`
- **Mapping Port & Hostname:**
  - `mongo1`: hostname `mongo1`, port `27017:27017`, mount dữ liệu mẫu `./products.json:/data/import/products.json:ro`
  - `mongo2`: hostname `mongo2`, port `27018:27018`
  - `mongo3`: hostname `mongo3`, port `27019:27019`
- **Volumes:** `mongo1_data`, `mongo2_data`, `mongo3_data` mount vào `/data/db`.

---

## 2. CẤU TRÚC BÀI THỰC HÀNH `HUONG_DAN_REPLICATION.md`

Tài liệu cần trình bày ngắn gọn, dễ thực hành, sử dụng lệnh `docker exec ... mongosh` kèm giải thích kết quả và bài học cốt lõi ("👉 **Kiến thức:**"):

### Mục 0: Khái niệm nền tảng
- Bảng giải thích: **Replica Set**, **PRIMARY** (duy nhất nhận ghi), **SECONDARY** (chỉ sao chép, cấm ghi), **Oplog** (`local.oplog.rs`), **Heartbeat** (mỗi 2s), **Election** (bầu cử khi Primary chết), **Majority** (> 1/2 số node).
- Sơ đồ Mermaid: Luồng Client $\rightarrow$ Primary $\rightarrow$ Oplog $\rightarrow$ Secondary kèm Heartbeat giữa các node.

### Mục 1 & 2: Khởi động và Khởi tạo cụm
- Khởi động: `docker compose up -d`. Chạy `rs.status()` trước khi khởi tạo để thấy lỗi `no replset config`.
- Khởi tạo trên `mongo1`:
  ```javascript
  rs.initiate({
    _id: "rs0",
    members: [
      { _id: 0, host: "mongo1:27017", priority: 2 },
      { _id: 1, host: "mongo2:27018", priority: 1 },
      { _id: 2, host: "mongo3:27019", priority: 1 }
    ]
  })
  ```
- Giải thích ý nghĩa của `priority: 2` (ưu tiên node làm Primary).

### Mục 3: Kiểm tra trạng thái Cluster
- Cấu hình tĩnh: `rs.conf()`.
- Trạng thái thời gian thực: `rs.status().members.map(m => ({ name: m.name, state: m.stateStr, health: m.health, syncFrom: m.syncSourceHost, optime: m.optimeDate }))`.
- Lệnh kiểm tra nhanh: `db.hello()`, `rs.printReplicationInfo()`, `rs.printSecondaryReplicationInfo()`.

### Mục 4: Nạp dữ liệu mẫu
- Dùng `mongoimport` với chuỗi kết nối cụm:
  `mongodb://mongo1:27017,mongo2:27018,mongo3:27019/?replicaSet=rs0`.
- 👉 **Kiến thức:** Client chỉ cần seed list, driver tự tìm Primary hiện tại để ghi.

### Mục 5: Thao tác Đọc/Ghi trên Primary và Secondary
- **Trên PRIMARY:**
  - Ghi dữ liệu (`insertOne`, `updateOne`).
  - Xem Oplog trên `local.oplog.rs` (các cờ `op: i/u/d`).
  - Thử nghiệm Write Concern: `w: 1` vs `w: "majority"`.
- **Trên SECONDARY:**
  - Thử ghi $\rightarrow$ Bị chặn với lỗi `not primary`.
  - Đọc dữ liệu: bật `db.getMongo().setReadPref("secondaryPreferred")`. Bảng 5 mức `readPreference` (`primary`, `primaryPreferred`, `secondary`, `secondaryPreferred`, `nearest`) và cảnh báo Stale Read.

### Mục 6: Minh họa Failover & Khả năng chịu lỗi (High Availability)
- **6.1. Primary sập (`docker stop mongo1`):** Sau 10s mất heartbeat, các node còn sống tự bầu Primary mới.
- **6.2. Ghi khi mất 1 node:** Dùng chuỗi kết nối replicaSet, thực hiện `insertOne` thành công $\rightarrow$ hệ thống không bị gián đoạn.
- **6.3. Node sống lại (`docker start mongo1`):** Trở về vai trò Secondary $\rightarrow$ tự catch-up oplog $\rightarrow$ giành lại quyền Primary (Priority Takeover).
- **6.4. Mất đa số (`docker stop mongo1 mongo2`):** Chỉ còn 1/3 node $\rightarrow$ không thể bầu Primary, chuyển sang Read-Only để chống **Split-Brain**.

### Mục 7 & 8: Bảng tổng kết & Phụ lục lệnh
- Bảng tóm tắt liên kết khái niệm với các bước thực hành.
- Lệnh dọn dẹp: `docker compose down -v`, lệnh xem log bầu cử: `docker logs -f <node> | grep -i election`.

---

## 3. NGUYÊN TẮC KHI CODE CHO AGENT
1. **Tiện lợi:** Mọi lệnh thực thi qua `docker exec` để người dùng không cần cài `mongosh`/tools trên máy host.
2. **Nhất quán:** Tên `--replSet` (`rs0`), cổng mạng và hostname phải đồng bộ giữa compose và tài liệu.
3. **Thực tiễn:** Giữ nguyên các thông báo lỗi kinh điển của MongoDB (`not primary`, `no replset config`) để người học nhận diện vấn đề.
