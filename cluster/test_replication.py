#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_replication.py - Kiểm thử ngắn gọn cụm MongoDB Replica Set (rs0).
Nội dung kiểm tra:
1. Kết nối (Connection)
2. Thông tin cụm (Cluster info: Primary/Secondary)
3. Ghi dữ liệu (Write: w="majority")
4. Đọc dữ liệu (Read: secondaryPreferred)
5. Kết quả từng node (Direct check: Online/Offline & doc count)
"""

import os
import socket
from datetime import datetime
from pymongo import MongoClient, ReadPreference, WriteConcern
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

REPLICA_SET = "rs0"
DB_NAME = "shop_online_db"
COLLECTION_NAME = "products"

NODES = [
    {"name": "mongo1", "port": 27017},
    {"name": "mongo2", "port": 27018},
    {"name": "mongo3", "port": 27019}
]

def is_resolvable(hostname: str) -> bool:
    try:
        socket.gethostbyname(hostname)
        return True
    except socket.error:
        return False

def get_mongo_hosts():
    # Trong Docker hoặc khi máy host đã cấu hình /etc/hosts
    if os.path.exists("/.dockerenv") or any(is_resolvable(n["name"]) for n in NODES):
        return [f"{n['name']}:{n['port']}" for n in NODES], "HOSTNAME"
    return [f"localhost:{n['port']}" for n in NODES], "LOCALHOST"

def main():
    hosts, host_type = get_mongo_hosts()
    uri = f"mongodb://{','.join(hosts)}/?replicaSet={REPLICA_SET}&serverSelectionTimeoutMS=4000"

    print("=" * 70)
    print("              KIỂM THỬ MONGODB REPLICA SET (rs0)")
    print("=" * 70)

    # 1. KẾT NỐI
    client = None
    try:
        client = MongoClient(uri)
        client.admin.command('ping')
        print(f"[1] Kết nối      : THÀNH CÔNG (Replica Set '{REPLICA_SET}')")
    except Exception as e:
        print(f"[1] Kết nối      : THẤT BẠI ({e})")
        return

    # 2. THÔNG TIN CỤM
    primary = client.primary
    secondaries = list(client.secondaries)
    primary_str = f"{primary[0]}:{primary[1]}" if primary else "None"
    secondaries_str = [f"{s[0]}:{s[1]}" for s in secondaries]
    print(f"[2] Thông tin cụm: PRIMARY -> {primary_str} | SECONDARY -> {secondaries_str}")

    # 3. GHI DỮ LIỆU VÀO PRIMARY
    inserted_id = None
    try:
        wc_majority = WriteConcern(w="majority", wtimeout=4000)
        col = client[DB_NAME].get_collection(COLLECTION_NAME, write_concern=wc_majority)
        sample = {
            "product_name": "Tai nghe Sony WH-1000XM5",
            "price": 6990000,
            "created_at": datetime.now(),
            "note": "Kiểm thử ghi w='majority'"
        }
        res = col.insert_one(sample)
        inserted_id = res.inserted_id
        print(f"[3] Ghi dữ liệu  : THÀNH CÔNG (ID: {inserted_id} | WriteConcern: majority)")
    except PyMongoError as e:
        print(f"[3] Ghi dữ liệu  : THẤT BẠI ({e})")

    # 4. ĐỌC DỮ LIỆU TỪ SECONDARY
    try:
        sec_db = client.get_database(DB_NAME, read_preference=ReadPreference.SECONDARY_PREFERRED)
        query = {"_id": inserted_id} if inserted_id else {}
        doc = sec_db[COLLECTION_NAME].find_one(query)
        if doc:
            print(f"[4] Đọc dữ liệu  : THÀNH CÔNG từ SECONDARY ('{doc.get('product_name')}' - {doc.get('price'):,}đ)")
        else:
            print("[4] Đọc dữ liệu  : Không tìm thấy document vừa ghi.")
    except PyMongoError as e:
        print(f"[4] Đọc dữ liệu  : THẤT BẠI ({e})")

    # 5. KẾT QUẢ TỪNG NODE
    print("[5] Kết quả các node:")
    for n in NODES:
        host = n["name"] if host_type == "HOSTNAME" else "localhost"
        direct_uri = f"mongodb://{host}:{n['port']}/?directConnection=true&serverSelectionTimeoutMS=1500"
        try:
            with MongoClient(direct_uri, read_preference=ReadPreference.SECONDARY_PREFERRED) as node_client:
                hello = node_client.admin.command('hello')
                role = "PRIMARY" if hello.get("isWritablePrimary") else "SECONDARY"
                count = node_client[DB_NAME][COLLECTION_NAME].count_documents({})
                print(f"    * {n['name']}:{n['port']} : [ONLINE] [{role}] - {count} documents")
        except Exception:
            print(f"    * {n['name']}:{n['port']} : [OFFLINE] (Node đang dừng)")

    print("=" * 70)
    client.close()

if __name__ == "__main__":
    main()