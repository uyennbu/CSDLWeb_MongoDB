# Setup MongoDB Replica Set 3 node – sample_mflix

| Node   | Container | Port (host = container) | Vai trò mong muốn |
|--------|-----------|-------------------------|-------------------|
| mflix1 | `mflix1`  | 27030                   | PRIMARY (priority 2) |
| mflix2 | `mflix2`  | 27031                   | SECONDARY |
| mflix3 | `mflix3`  | 27032                   | SECONDARY |

> Dùng port 27030–27032 để **không đụng** cluster trong thư mục `cluster/` (27017–27019).
> Máy host không cần cài `mongosh`/`mongorestore` – mọi lệnh chạy qua `docker exec` (image `mongo` có sẵn tools).

Tất cả lệnh chạy trong thư mục `sample_mflix/`.

---

## Bước 1 – Khởi động 3 container

```bash
docker compose up -d
docker compose ps        # 3 container mflix1/2/3 phải ở trạng thái "Up"
```

## Bước 2 – Khởi tạo Replica Set (chỉ làm 1 lần)

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

Chờ ~10 giây để bầu PRIMARY.

## Bước 3 – Kiểm tra sơ lược trạng thái các node

```bash
docker exec mflix1 mongosh --port 27030 --quiet --eval '
rs.status().members.forEach(m => print(m.name, "->", m.stateStr))'
```

Kết quả mong đợi:

```
mflix1:27030 -> PRIMARY
mflix2:27031 -> SECONDARY
mflix3:27032 -> SECONDARY
```

## Bước 4 – Nạp dữ liệu sample_mflix

File `sampledata.archive` đã được mount vào `mflix1` tại `/data/import/sampledata.archive`.

```bash
docker exec mflix1 mongorestore --port 27030 \
  --archive=/data/import/sampledata.archive \
  --nsInclude='sample_mflix.*'
```

> [!NOTE]
> - File này **không nén gzip** nên **không dùng** `--gzip` (nếu thêm sẽ báo lỗi).
> - File chứa toàn bộ bộ sample của Atlas; `--nsInclude='sample_mflix.*'` chỉ nạp DB `sample_mflix`.
>   Bỏ tham số này nếu muốn nạp tất cả.
> - Phải restore vào node **PRIMARY** (port 27030).

## Bước 5 – Kiểm tra dữ liệu

```bash
docker exec mflix1 mongosh --port 27030 --quiet --eval '
db = db.getSiblingDB("sample_mflix");
db.getCollectionNames().forEach(c => print(c, db[c].countDocuments()))'
```

Kiểm tra dữ liệu đã **replicate** sang secondary:

```bash
docker exec mflix2 mongosh --port 27031 --quiet --eval '
db.getMongo().setReadPref("secondary");
print(db.getSiblingDB("sample_mflix").movies.countDocuments())'
```

## Bước 6 – Chuỗi kết nối cho UI

**Cách đơn giản (kết nối thẳng vào PRIMARY):**

```
mongodb://localhost:27030/sample_mflix?directConnection=true
```

**Cách đầy đủ (kết nối Replica Set – tự failover):** thêm vào `/etc/hosts` của máy host:

```
127.0.0.1  mflix1 mflix2 mflix3
```

rồi dùng:

```
mongodb://mflix1:27030,mflix2:27031,mflix3:27032/sample_mflix?replicaSet=rsMflix
```

---

## Lệnh hữu ích

```bash
docker exec -it mflix1 mongosh --port 27030   # mở shell tương tác
docker compose stop                            # dừng (giữ dữ liệu)
docker compose start                           # chạy lại (không cần rs.initiate nữa)
docker compose down -v                         # xoá hết, kể cả dữ liệu -> làm lại từ Bước 1
```
