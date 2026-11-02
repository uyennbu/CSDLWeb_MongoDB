# Thực Hành & Demo Chuyên Sâu MongoDB

Dự án cung cấp môi trường thực hành Docker và Web UI trực quan nhằm minh họa các tính năng cốt lõi của **MongoDB**: từ truy vấn cơ bản, Aggregation, Full-Text Search đến kiến trúc phân tán **Replication** (Chịu lỗi - HA) và **Sharding** (Mở rộng ngang - Scale-out).

---

## 1. Các Chức Năng Được Minh Họa

1. **CRUD & Truy Vấn Nâng Cao:** Thao tác thêm, sửa, xóa, tìm kiếm regex và thống kê tài liệu.
2. **MongoDB Full-Text Search (`$text`):** Tận dụng Text Index với trọng số (`weights`), tính toán và xếp hạng theo điểm liên quan `textScore`.
3. **Aggregation Pipeline:** Phân tích dữ liệu nhiều tầng với các stage `$unwind`, `$group`, `$match`, `$sort`, `$limit`.
4. **Replication (Replica Set 3 Node):** Cơ chế Single-Leader, đồng bộ dữ liệu qua Oplog, Write Concern, Read Preference và tự động bầu cử khi Primary chết (Automatic Failover).
5. **Sharding (Cluster Phân Mảnh):** Định tuyến truy vấn qua `mongos`, lưu metadata trên Config Server, so sánh Range Sharding vs Hashed Sharding, và phân tích truy vấn Targeted vs Scatter-Gather.

---

## 2. Cấu Trúc Dự Án

```text
CSDLWeb_MongoDB/
├── cluster/             # Cụm Docker thực hành Replication & Sharding qua dòng lệnh
│   ├── docker-compose.yml
│   ├── HUONG_DAN_REPLICATION.md   # Bài thực hành chi tiết Replica Set 3 node
│   ├── HUONG_DAN_SHARDING.md       # Bài thực hành chi tiết Sharded Cluster
│   └── products.json              # Dữ liệu mẫu shop sản phẩm
├── sample_mflix/        # Web Demo trực quan (Python Flask + MongoDB Replica Set)
│   ├── docker-compose.yml         # Cụm 3 node (ports 27030-27032)
│   ├── app.py                     # Flask API backend hỗ trợ tự động failover
│   ├── templates/ & static/       # Giao diện SPA tối giản (Beige - White - Light Gray)
│   ├── SETUP.md                   # Khởi tạo cluster & nạp sampledata
│   └── RUN_WEB.md                 # Hướng dẫn chạy Web UI
├── single/              # Các tập lệnh truy vấn mẫu mongosh (CRUD, Aggregation)
└── docs/                # Đặc tả prompt để AI Agent code lại từng phần dự án
    ├── CLUSTER_REPLICATION.md
    ├── CLUSTER_SHARDING.md
    └── UI_DEMO.md
```

---

## 3. Hướng Dẫn Thực Hành Nhanh

### Cách 1: Thực hành Dòng lệnh Cluster (`cluster/`)
- **Replication (3 node):**
  ```bash
  cd cluster
  docker compose up -d
  # Làm theo hướng dẫn chi tiết tại: cluster/HUONG_DAN_REPLICATION.md
  ```
- **Sharding (Config Server + 3 Shards + mongos):**
  ```bash
  cd cluster
  docker compose --profile sharding up -d
  # Làm theo hướng dẫn chi tiết tại: cluster/HUONG_DAN_SHARDING.md
  ```

### Cách 2: Trải nghiệm Giao diện Trực quan (`sample_mflix/`)
1. **Dựng cụm MongoDB & nạp dữ liệu:**
   ```bash
   cd sample_mflix
   docker compose up -d
   # Xem các lệnh khởi tạo cụm và import archive tại SETUP.md
   ```
2. **Chạy Web Server:**
   ```bash
   pip install -r requirements.txt
   python3 app.py
   ```
3. Mở trình duyệt tại `http://localhost:5000` để trải nghiệm trực quan CRUD, Text Search, Aggregation và thử nghiệm tắt/bật node để kiểm tra High Availability.
