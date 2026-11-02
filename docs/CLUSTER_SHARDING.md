# HƯỚNG DẪN AI AGENT: TRIỂN KHAI MONGODB SHARDING CLUSTER

> **Mục đích:** Prompt chuẩn để AI Agent tự động code/cập nhật 2 file: `docker-compose.yml` (bổ sung profile sharding) và `HUONG_DAN_SHARDING.md` cho bài thực hành MongoDB Sharding.

---

## 1. YÊU CẦU FILE `docker-compose.yml` (PROFILE: `sharding`)

Cụm Sharding chạy song song trong cùng mạng `mongo-cluster` với bài Replication, kích hoạt qua cờ `profiles: ["sharding"]`:

- **Config Server (`cfg1`):**
  - Image: `mongo:latest`, hostname: `cfg1`, container_name: `cfg1`.
  - Command: `["mongod", "--configsvr", "--replSet", "cfgRS", "--bind_ip_all", "--port", "27017"]`.
  - Volume: `cfg1_data:/data/db`.
- **3 Shards (`shard1`, `shard2`, `shard3`):**
  - Image: `mongo:latest`, hostname/container_name tương ứng.
  - Command: `["mongod", "--shardsvr", "--replSet", "<shard_name>RS", "--bind_ip_all", "--port", "27017"]`.
    *(Ví dụ: `shard1RS`, `shard2RS`, `shard3RS`)*.
  - Volumes: `shard1_data:/data/db`, `shard2_data:/data/db`, `shard3_data:/data/db`.
- **Router (`mongos`):**
  - Image: `mongo:latest`, hostname/container_name: `mongos`.
  - Command: `["mongos", "--configdb", "cfgRS/cfg1:27017", "--bind_ip_all", "--port", "27017"]`.
  - Restart: `unless-stopped` (tự restart chờ Config Server sẵn sàng).
  - Port mapping: `"27030:27017"` (mở cổng 27030 trên máy host để client/web kết nối).
  - Volume: Mount dữ liệu mẫu `./products.json:/data/import/products.json:ro`.
  - Depends on: `[cfg1, shard1, shard2, shard3]`.

---

## 2. CẤU TRÚC BÀI THỰC HÀNH `HUONG_DAN_SHARDING.md`

Tài liệu cần cô đọng, dễ hiểu, sử dụng `docker exec ... mongosh` kèm giải thích bài học cốt lõi ("👉 **Kiến thức:**"):

### Mục 0: Khái niệm nền tảng
- So sánh: **Replication** (sao chép để chịu lỗi HA) vs **Sharding** (chia nhỏ để scale-out mở rộng ngang).
- Bảng giải thích: **Shard** (lưu 1 phần dữ liệu), **Config Server** (lưu metadata chunk), **mongos** (router chuyển tiếp truy vấn), **Shard Key** (khóa phân vùng), **Chunk** (khoảng giá trị liên tục), **Balancer** (tiến trình cân bằng chunk).
- Sơ đồ Mermaid: Client $\rightarrow$ mongos $\rightarrow$ Config Server & các Shard.

### Mục 1 & 2: Khởi động và Khởi tạo Cluster
- Chạy: `docker compose --profile sharding up -d`.
- **Khởi tạo Config Server:** Trên `cfg1`, chạy `rs.initiate({ _id: "cfgRS", configsvr: true, members: [{ _id: 0, host: "cfg1:27017" }] })`.
- **Khởi tạo từng Shard:** Trên `shard1`, `shard2`, `shard3`, khởi tạo replica set đơn node (`shard1RS/shard1:27017`, `shard2RS/shard2:27017`, `shard3RS/shard3:27017`).
- **Thêm Shard vào Cluster (trên `mongos`):**
  `sh.addShard("shard1RS/shard1:27017")`, tương tự cho `shard2RS`, `shard3RS`.
- 👉 **Kiến thức:** Kể từ đây, mọi thao tác của Client đều đi qua `mongos`.

### Mục 3: Xem cấu trúc Cluster
- Lệnh kiểm tra trên `mongos`: `sh.status()`, `db.adminCommand({ listShards: 1 })`, `sh.getBalancerState()`.

### Mục 4: Phân mảnh Collection & Nạp dữ liệu
- **4.1. Range Sharding (theo `{ price: 1 }`):**
  - `sh.enableSharding("shop")`.
  - `sh.shardCollection("shop.products", { price: 1 })`.
  - Tắt balancer: `sh.stopBalancer()`.
  - Chia chunk thủ công: `sh.splitAt("shop.products", { price: 1000000 })`, `{ price: 2000000 }`.
  - Di chuyển chunk: `sh.moveChunk` đưa 3 khoảng `< 1tr`, `1tr - 2tr`, `> 2tr` lần lượt vào 3 shard.
  - Import dữ liệu qua `mongos` bằng `mongoimport`.
  - Kiểm tra phân bổ: `db.products.getShardDistribution()`.
- **4.2. Hashed Sharding (theo `{ _id: "hashed" }`):**
  - Shard collection dạng hash: `sh.shardCollection("shop.products_hashed", { _id: "hashed" })`.
  - Import và kiểm tra: dữ liệu tự động rải đều qua cả 3 shard.
  - Bảng so sánh Range Sharding vs Hashed Sharding.

### Mục 5: So sánh Định tuyến Truy vấn (Targeted vs Scatter-Gather)
Dùng `cursor.explain().queryPlanner.winningPlan` để xem số shard nhận lệnh:
- **Đọc có Shard Key (Targeted Query):** Chỉ gửi tới 1 shard (`SINGLE_SHARD`) hoặc các shard liên quan $\rightarrow$ Cực nhanh.
- **Đọc KHÔNG có Shard Key (Scatter-Gather):** Bắt buộc hỏi TẤT CẢ các shard (`SHARD_MERGE`) $\rightarrow$ Chậm, tốn tài nguyên.
- **Ghi dữ liệu:** `mongos` tự động căn cứ Shard Key để lưu vào đúng Shard mà app không cần can thiệp.

### Mục 6: Thử nghiệm khi 1 Shard bị sập (`docker stop shard2`)
- **Dữ liệu ở shard khác (1 & 3):** Vẫn đọc/ghi bình thường.
- **Dữ liệu ở shard bị sập:** Lỗi timeout. Lệnh toàn cục (`countDocuments()`) cũng lỗi trừ khi dùng `.allowPartialResults()`.
- 👉 **Kiến thức:** Sharding chỉ lo **mở rộng**, không lo **chịu lỗi**. Muốn chịu lỗi, mỗi shard trong thực tế phải là một Replica Set 3 node (kết hợp cả Replication + Sharding).

### Mục 7 & 8: Bảng tổng kết & Phụ lục lệnh
- Bảng tóm tắt liên kết các kiến thức cốt lõi.
- Lệnh dừng: `docker compose --profile sharding stop cfg1 shard1 shard2 shard3 mongos`.
- Lệnh xóa sạch: `docker compose --profile sharding down -v`.

---

## 3. NGUYÊN TẮC KHI CODE CHO AGENT
1. **Dùng Profile:** Bắt buộc dùng `profiles: ["sharding"]` để không tự động chạy các container sharding khi người dùng chỉ muốn thực hành bài Replication.
2. **Cổng Host độc lập:** Port của `mongos` (vd: `27030`) không được trùng với cổng các node `mongo1..3` (`27017..27019`).
3. **Thứ tự khởi tạo:** Bắt buộc khởi tạo Config Server trước, các Shard sau, rồi mới add shard qua `mongos`.

