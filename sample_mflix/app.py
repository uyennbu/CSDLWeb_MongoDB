import os
from datetime import datetime
from bson import ObjectId
from flask import Flask, render_template, request, jsonify
import pymongo
from pymongo import MongoClient

app = Flask(__name__)

# Kết nối MongoDB Replica Set hoặc trực tiếp tới node Primary (port 27030)
# Thử kết nối replica set, nếu không có hostname mapping sẽ fallback directConnection=true
MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb://localhost:27030,localhost:27031,localhost:27032/sample_mflix?replicaSet=rsMflix&directConnection=true"
)

try:
    client = MongoClient(
        "mongodb://localhost:27030/sample_mflix?directConnection=true",
        serverSelectionTimeoutMS=3000
    )
    db = client["sample_mflix"]
    # Test connection
    client.admin.command('ping')
except Exception as e:
    print(f"Lỗi kết nối MongoDB: {e}")
    db = None

def serialize_doc(doc):
    """Chuyển đổi ObjectId và Datetime sang định dạng JSON serialize được"""
    if not doc:
        return doc
    if isinstance(doc, list):
        return [serialize_doc(item) for item in doc]
    if isinstance(doc, dict):
        new_doc = {}
        for k, v in doc.items():
            if isinstance(v, ObjectId):
                new_doc[k] = str(v)
            elif isinstance(v, datetime):
                new_doc[k] = v.isoformat()
            elif isinstance(v, (dict, list)):
                new_doc[k] = serialize_doc(v)
            else:
                new_doc[k] = v
        return new_doc
    return doc

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status", methods=["GET"])
def get_status():
    """Kiểm tra trạng thái cluster và đếm số lượng tài liệu"""
    if db is None:
        return jsonify({"status": "error", "message": "Không thể kết nối MongoDB"}), 500
    try:
        movie_count = db.movies.count_documents({})
        comment_count = db.comments.count_documents({})
        theaters_count = db.theaters.count_documents({})
        users_count = db.users.count_documents({})
        return jsonify({
            "status": "connected",
            "counts": {
                "movies": movie_count,
                "comments": comment_count,
                "theaters": theaters_count,
                "users": users_count
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ==========================================
# 1. CRUD API - MOVIES
# ==========================================

@app.route("/api/movies", methods=["GET"])
def list_movies():
    """READ: Tìm kiếm và phân trang phim"""
    try:
        q = request.args.get("q", "").strip()
        genre = request.args.get("genre", "").strip()
        mode = request.args.get("mode", "regex").strip()  # 'regex' hoặc 'text'
        limit = min(int(request.args.get("limit", 12)), 50)
        skip = int(request.args.get("skip", 0))

        filter_query = {}
        projection = {
            "title": 1, "year": 1, "genres": 1, "imdb": 1, "plot": 1, "poster": 1, "cast": 1
        }
        sort_criteria = [("year", -1)]

        if q:
            if mode == "text":
                # Full-Text Search qua MongoDB Text Index
                filter_query["$text"] = {"$search": q}
                projection["score"] = {"$meta": "textScore"}
                sort_criteria = [("score", {"$meta": "textScore"})]
            else:
                # Tìm kiếm Regex thông thường theo tiêu đề
                filter_query["title"] = {"$regex": q, "$options": "i"}

        if genre:
            filter_query["genres"] = genre

        if mode == "text" and q:
            cursor = db.movies.find(filter_query, projection).sort(sort_criteria).skip(skip).limit(limit)
        else:
            cursor = db.movies.find(filter_query, projection).sort(sort_criteria).skip(skip).limit(limit)

        movies = list(cursor)
        # Làm tròn score nếu có
        for m in movies:
            if "score" in m and isinstance(m["score"], float):
                m["score"] = round(m["score"], 2)

        total = db.movies.count_documents(filter_query)

        # Lấy danh sách thể loại phổ biến để lọc
        genres = db.movies.distinct("genres")
        clean_genres = sorted([g for g in genres if g and isinstance(g, str)])[:25]

        # Mô tả câu lệnh MongoDB
        if mode == "text" and q:
            mongo_code = f"db.movies.find(\n  {{ $text: {{ $search: \"{q}\" }} }},\n  {{ title: 1, year: 1, score: {{ $meta: 'textScore' }} }}\n).sort({{ score: {{ $meta: 'textScore' }} }}).limit({limit})"
        else:
            mongo_code = f"db.movies.find({filter_query}, {{ title: 1, year: 1, genres: 1 }}).sort({{ year: -1 }}).limit({limit})"

        return jsonify({
            "total": total,
            "movies": serialize_doc(movies),
            "genres": clean_genres,
            "mode": mode,
            "query_used": filter_query,
            "mongo_command": mongo_code
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/movies/<movie_id>", methods=["GET"])
def get_movie(movie_id):
    """READ: Chi tiết 1 phim theo _id"""
    try:
        movie = db.movies.find_one({"_id": ObjectId(movie_id)})
        if not movie:
            return jsonify({"error": "Không tìm thấy phim"}), 404
        return jsonify(serialize_doc(movie))
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/movies", methods=["POST"])
def create_movie():
    """CREATE: Thêm phim mới (insert_one)"""
    try:
        data = request.json or {}
        title = data.get("title", "").strip()
        if not title:
            return jsonify({"error": "Tiêu đề phim (title) là bắt buộc"}), 400

        doc = {
            "title": title,
            "year": int(data.get("year", 2026)),
            "genres": [g.strip() for g in data.get("genres", []) if g.strip()],
            "plot": data.get("plot", ""),
            "cast": [c.strip() for c in data.get("cast", []) if c.strip()],
            "imdb": {
                "rating": float(data.get("rating", 7.0)),
                "votes": 1
            },
            "createdAt": datetime.utcnow()
        }

        result = db.movies.insert_one(doc)
        doc["_id"] = str(result.inserted_id)
        return jsonify({
            "message": "Thêm phim thành công!",
            "inserted_id": str(result.inserted_id),
            "movie": serialize_doc(doc),
            "mongo_command": "db.movies.insertOne({...})"
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/movies/<movie_id>", methods=["PUT"])
def update_movie(movie_id):
    """UPDATE: Cập nhật thông tin phim (update_one với $set)"""
    try:
        data = request.json or {}
        update_fields = {}

        if "title" in data:
            update_fields["title"] = data["title"].strip()
        if "year" in data:
            update_fields["year"] = int(data["year"])
        if "plot" in data:
            update_fields["plot"] = data["plot"]
        if "rating" in data:
            update_fields["imdb.rating"] = float(data["rating"])
        if "genres" in data:
            update_fields["genres"] = [g.strip() for g in data["genres"] if g.strip()]

        if not update_fields:
            return jsonify({"error": "Không có trường nào để cập nhật"}), 400

        update_fields["updatedAt"] = datetime.utcnow()

        result = db.movies.update_one(
            {"_id": ObjectId(movie_id)},
            {"$set": update_fields}
        )

        if result.matched_count == 0:
            return jsonify({"error": "Không tìm thấy phim để sửa"}), 404

        return jsonify({
            "message": "Cập nhật phim thành công!",
            "modified_count": result.modified_count,
            "mongo_command": f"db.movies.updateOne({{ _id: ObjectId('{movie_id}') }}, {{ $set: {update_fields} }})"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/movies/<movie_id>", methods=["DELETE"])
def delete_movie(movie_id):
    """DELETE: Xoá phim (delete_one)"""
    try:
        result = db.movies.delete_one({"_id": ObjectId(movie_id)})
        if result.deleted_count == 0:
            return jsonify({"error": "Không tìm thấy phim để xóa"}), 404
        return jsonify({
            "message": "Xoá phim thành công!",
            "deleted_count": result.deleted_count,
            "mongo_command": f"db.movies.deleteOne({{ _id: ObjectId('{movie_id}') }})"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# 2. AGGREGATION PIPELINE DEMOS
# ==========================================

@app.route("/api/aggregate/genres-stats", methods=["GET"])
def agg_genres_stats():
    """
    Aggregation 1: Thống kê số lượng phim và điểm IMDb trung bình theo từng Thể loại
    Stages: $unwind -> $group -> $sort -> $limit
    """
    try:
        pipeline = [
            {"$unwind": "$genres"},
            {
                "$group": {
                    "_id": "$genres",
                    "totalMovies": {"$sum": 1},
                    "avgRating": {"$avg": "$imdb.rating"},
                    "maxRating": {"$max": "$imdb.rating"}
                }
            },
            {"$match": {"totalMovies": {"$gte": 50}}},
            {"$sort": {"totalMovies": -1}},
            {"$limit": 15}
        ]

        result = list(db.movies.aggregate(pipeline))
        for r in result:
            if r.get("avgRating") is not None:
                r["avgRating"] = round(r["avgRating"], 2)

        return jsonify({
            "title": "Top thể loại theo số lượng phim & IMDb trung bình",
            "pipeline": pipeline,
            "result": serialize_doc(result)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/aggregate/top-rated-by-year", methods=["GET"])
def agg_top_rated_by_year():
    """
    Aggregation 2: Top phim điểm IMDb cao nhất theo từng thập kỷ/năm
    Stages: $match -> $sort -> $group (nhặt $first) -> $sort
    """
    try:
        min_year = int(request.args.get("min_year", 1990))
        pipeline = [
            {
                "$match": {
                    "year": {"$gte": min_year, "$lte": 2020},
                    "imdb.rating": {"$exists": True, "$type": "number"},
                    "imdb.votes": {"$gte": 10000}
                }
            },
            {"$sort": {"imdb.rating": -1}},
            {
                "$group": {
                    "_id": "$year",
                    "topMovie": {"$first": "$title"},
                    "highestRating": {"$first": "$imdb.rating"},
                    "votes": {"$first": "$imdb.votes"},
                    "genres": {"$first": "$genres"}
                }
            },
            {"$sort": {"_id": -1}},
            {"$limit": 12}
        ]

        result = list(db.movies.aggregate(pipeline))
        return jsonify({
            "title": f"Phim điểm cao nhất mỗi năm (có ít nhất 10.000 lượt vote từ {min_year})",
            "pipeline": pipeline,
            "result": serialize_doc(result)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/aggregate/movies-comments-lookup", methods=["GET"])
def agg_movies_lookup():
    """
    Aggregation 3: $lookup (JOIN) nối bảng movies với comments
    Lấy danh sách các phim có nhiều bình luận nhất
    """
    try:
        pipeline = [
            {
                "$lookup": {
                    "from": "comments",
                    "localField": "_id",
                    "foreignField": "movie_id",
                    "as": "movie_comments"
                }
            },
            {
                "$project": {
                    "title": 1,
                    "year": 1,
                    "genres": 1,
                    "commentCount": {"$size": "$movie_comments"},
                    "latestComment": {
                        "$slice": ["$movie_comments.text", 2]
                    }
                }
            },
            {"$sort": {"commentCount": -1}},
            {"$limit": 8}
        ]

        result = list(db.movies.aggregate(pipeline))
        return jsonify({
            "title": "Lookup (JOIN): Phim có nhiều bình luận nhất từ collection 'comments'",
            "pipeline": pipeline,
            "result": serialize_doc(result)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/aggregate/custom", methods=["POST"])
def agg_custom():
    """Cho phép người dùng kiểm tra pipeline JSON tùy biến"""
    try:
        data = request.json or {}
        pipeline = data.get("pipeline", [])
        if not isinstance(pipeline, list):
            return jsonify({"error": "Pipeline phải là mảng các stage [ {...}, {...} ]"}), 400
        
        result = list(db.movies.aggregate(pipeline))
        return jsonify({
            "pipeline": pipeline,
            "count": len(result),
            "result": serialize_doc(result[:30])
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ==========================================
# 3. REPLICATION DEMO APIS
# ==========================================

NODES_CONFIG = [
    {"name": "mflix1", "port": 27030, "container": "mflix1"},
    {"name": "mflix2", "port": 27031, "container": "mflix2"},
    {"name": "mflix3", "port": 27032, "container": "mflix3"}
]

@app.route("/api/replication/status", methods=["GET"])
def get_replication_status():
    """Lấy trạng thái chi tiết của từng Node trong Replica Set (Primary/Secondary/Down) và số lượng document"""
    nodes_info = []
    rs_summary = {}

    # Thử lấy rs.status() từ một node đang sống
    for cfg in NODES_CONFIG:
        try:
            c = MongoClient(f"mongodb://localhost:{cfg['port']}/?directConnection=true", serverSelectionTimeoutMS=800)
            status_cmd = c.admin.command("replSetGetStatus")
            rs_summary["set"] = status_cmd.get("set")
            rs_summary["date"] = status_cmd.get("date")
            break
        except Exception:
            continue

    for cfg in NODES_CONFIG:
        node_res = {
            "name": cfg["name"],
            "port": cfg["port"],
            "container": cfg["container"],
            "state": "DOWN",
            "isPrimary": False,
            "isSecondary": False,
            "movieCount": 0,
            "optime": None,
            "pingMs": None,
            "error": None
        }
        try:
            import time
            start = time.perf_counter()
            c = MongoClient(
                f"mongodb://localhost:{cfg['port']}/?directConnection=true",
                serverSelectionTimeoutMS=1000
            )
            is_master = c.admin.command("isMaster")
            node_res["pingMs"] = round((time.perf_counter() - start) * 1000, 1)

            if is_master.get("ismaster"):
                node_res["state"] = "PRIMARY"
                node_res["isPrimary"] = True
            elif is_master.get("secondary"):
                node_res["state"] = "SECONDARY"
                node_res["isSecondary"] = True
            else:
                node_res["state"] = "OTHER"

            # Đọc số lượng phim từ node này (với Secondary cần readPreference='secondaryPreferred')
            db_node = c.get_database("sample_mflix", read_preference=pymongo.read_preferences.ReadPreference.SECONDARY_PREFERRED)
            node_res["movieCount"] = db_node.movies.count_documents({})
        except Exception as e:
            node_res["state"] = "DOWN"
            node_res["error"] = str(e)

        nodes_info.append(node_res)

    return jsonify({
        "nodes": nodes_info,
        "summary": rs_summary
    })

@app.route("/api/replication/node-action", methods=["POST"])
def toggle_node():
    """Điều khiển dừng hoặc khởi động container Docker tương ứng với node (để demo Failover / High Availability)"""
    import subprocess
    data = request.json or {}
    container = data.get("container")
    action = data.get("action")  # 'stop' hoặc 'start'

    if container not in ["mflix1", "mflix2", "mflix3"]:
        return jsonify({"error": "Tên container không hợp lệ"}), 400
    if action not in ["stop", "start"]:
        return jsonify({"error": "Hành động chỉ có thể là stop hoặc start"}), 400

    try:
        cmd = ["docker", action, container]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return jsonify({
            "message": f"Đã thực hiện lệnh: {' '.join(cmd)} thành công!",
            "container": container,
            "action": action
        })
    except Exception as e:
        return jsonify({"error": f"Lỗi khi thực thi docker: {str(e)}"}), 500

@app.route("/api/replication/sync-test", methods=["POST"])
def replication_sync_test():
    """Ghi 1 document vào Primary và kiểm tra xem cả 3 node đã đồng bộ (Replicated) chưa"""
    try:
        test_title = f"Replication Test Record - {datetime.utcnow().strftime('%H:%M:%S')}"
        doc = {
            "title": test_title,
            "year": 2026,
            "genres": ["Test", "Replication"],
            "plot": "Document dùng để kiểm tra tính năng đồng bộ dữ liệu tự động giữa Primary và Secondary.",
            "isReplicationTest": True,
            "createdAt": datetime.utcnow()
        }

        # Ghi vào Primary qua kết nối thông thường
        insert_res = db.movies.insert_one(doc)
        inserted_id = str(insert_res.inserted_id)

        # Kiểm tra sự tồn tại trên từng node
        import time
        time.sleep(0.3)  # Đợi replication lag nhỏ

        check_results = []
        for cfg in NODES_CONFIG:
            found = False
            state = "DOWN"
            try:
                c = MongoClient(f"mongodb://localhost:{cfg['port']}/?directConnection=true", serverSelectionTimeoutMS=800)
                db_node = c.get_database("sample_mflix", read_preference=pymongo.read_preferences.ReadPreference.SECONDARY_PREFERRED)
                res = db_node.movies.find_one({"_id": ObjectId(inserted_id)})
                if res:
                    found = True
                is_master = c.admin.command("isMaster")
                state = "PRIMARY" if is_master.get("ismaster") else ("SECONDARY" if is_master.get("secondary") else "OTHER")
            except Exception:
                found = False
                state = "DOWN"

            check_results.append({
                "node": cfg["name"],
                "port": cfg["port"],
                "state": state,
                "replicated": found
            })

        return jsonify({
            "message": "Đã ghi dữ liệu vào PRIMARY và kiểm tra đồng bộ sang các SECONDARY!",
            "test_title": test_title,
            "inserted_id": inserted_id,
            "results": check_results
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# 4. SHARDING DEMO APIS
# ==========================================

# Mô hình Sharding 3 Shard (dựa trên Shard Key 'year' cho movies hoặc khoảng giá 'price')
SHARD_RANGES = [
    {
        "id": "shard1RS",
        "name": "Shard 1 (shard1RS)",
        "host": "shard1:27017",
        "keyRange": "year < 1980 (Phim cổ điển)",
        "description": "Lưu trữ các bộ phim phát hành trước năm 1980",
        "filter": {"year": {"$lt": 1980}}
    },
    {
        "id": "shard2RS",
        "name": "Shard 2 (shard2RS)",
        "host": "shard2:27017",
        "keyRange": "1980 <= year < 2000 (Thời kỳ hoàng kim)",
        "description": "Lưu trữ các bộ phim từ năm 1980 đến 1999",
        "filter": {"year": {"$gte": 1980, "$lt": 2000}}
    },
    {
        "id": "shard3RS",
        "name": "Shard 3 (shard3RS)",
        "host": "shard3:27017",
        "keyRange": "year >= 2000 (Điện ảnh hiện đại)",
        "description": "Lưu trữ các bộ phim từ năm 2000 trở đi",
        "filter": {"year": {"$gte": 2000}}
    }
]

@app.route("/api/sharding/status", methods=["GET"])
def get_sharding_status():
    """Thống kê phân bổ dữ liệu Sharding theo Shard Key (giả lập hoặc kết nối sharding cluster thật nếu có)"""
    try:
        shards_info = []
        total_movies = db.movies.count_documents({})

        for s in SHARD_RANGES:
            count = db.movies.count_documents(s["filter"])
            pct = round((count / total_movies * 100), 1) if total_movies > 0 else 0
            shards_info.append({
                "id": s["id"],
                "name": s["name"],
                "host": s["host"],
                "keyRange": s["keyRange"],
                "description": s["description"],
                "documentCount": count,
                "percentage": pct
            })

        return jsonify({
            "shardKey": "year (Range-based Sharding)",
            "mongosRouter": "mongos:27017 (Client Gateway)",
            "configServer": "cfgRS/cfg1:27017 (Metadata & Chunk Catalog)",
            "totalDocuments": total_movies,
            "shards": shards_info
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/sharding/route-explain", methods=["POST"])
def explain_sharding_route():
    """
    Minh họa cách Router (mongos) định tuyến truy vấn:
    - Targeted Query (Đơn Shard): Nếu có Shard Key ('year') -> Chỉ gửi đúng 1 Shard liên quan (cực nhanh).
    - Multi-Shard Query: Nếu Shard Key trải qua 2 khoảng.
    - Scatter-Gather Query: Nếu KHÔNG có Shard Key -> Phải phát tán tới TẤT CẢ các Shard rồi gộp kết quả.
    """
    try:
        data = request.json or {}
        query_type = data.get("query_type", "targeted")  # 'targeted_single', 'targeted_range', 'scatter_gather'

        if query_type == "targeted_single":
            # Ví dụ: find({ year: 1995, title: /Toy Story/ })
            year_val = int(data.get("year", 1995))
            target_shard = "shard1RS" if year_val < 1980 else ("shard2RS" if year_val < 2000 else "shard3RS")
            sample_query = {"year": year_val}
            return jsonify({
                "queryType": "Targeted Query (Single Shard Routing)",
                "explanation": f"Truy vấn chứa chính xác Shard Key 'year = {year_val}'. Mongos tra cứu Config Server và gửi thẳng truy vấn tới DUY NHẤT 1 Shard mà không làm phiền các Shard khác.",
                "routingStage": "SINGLE_SHARD",
                "targetedShards": [target_shard],
                "sampleQuery": sample_query,
                "performance": "⚡ Cực nhanh (Tối ưu hóa tài nguyên mạng và CPU)"
            })

        elif query_type == "targeted_range":
            # Ví dụ: find({ year: { $gte: 1975, $lte: 1985 } })
            sample_query = {"year": {"$gte": 1975, "$lte": 1985}}
            return jsonify({
                "queryType": "Targeted Range Query (Multi-Shard Route)",
                "explanation": "Truy vấn tìm theo khoảng năm (1975 - 1985), khoảng này vắt ngang qua Shard 1 (<1980) và Shard 2 (1980-1999). Mongos chỉ cần gửi yêu cầu đến đúng 2 Shard này và gộp kết quả.",
                "routingStage": "SHARD_MERGE (2 Shards)",
                "targetedShards": ["shard1RS", "shard2RS"],
                "sampleQuery": sample_query,
                "performance": "👍 Nhanh (Chỉ truy cập đúng các Shard chứa dữ liệu)"
            })

        else:
            # Ví dụ: find({ genres: "Action" }) -> Không có shard key!
            sample_query = {"genres": "Action"}
            return jsonify({
                "queryType": "Scatter-Gather Query (Phát tán toàn cụm)",
                "explanation": "Truy vấn KHÔNG chứa Shard Key (tìm theo 'genres'). Mongos không biết phim nằm ở đâu nên BẮT BUỘC phải gửi truy vấn tới TẤT CẢ các Shard trong hệ thống (Broadcast), sau đó gom kết quả về sắp xếp.",
                "routingStage": "SHARD_MERGE (Broadcast all Shards)",
                "targetedShards": ["shard1RS", "shard2RS", "shard3RS"],
                "sampleQuery": sample_query,
                "performance": "⚠️ Chậm và tốn tài nguyên (Cần tránh trong các hệ thống lớn)"
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/sharding/insert-route", methods=["POST"])
def simulate_sharding_insert():
    """Minh họa router tự động định tuyến khi thêm mới document dựa vào Shard Key"""
    try:
        data = request.json or {}
        year = int(data.get("year", 2026))
        title = data.get("title", "Sample Movie")

        target_shard = "shard1RS" if year < 1980 else ("shard2RS" if year < 2000 else "shard3RS")
        return jsonify({
            "message": f"Dựa vào Shard Key year={year}, Mongos tự động định tuyến bản ghi '{title}' vào đúng shard: {target_shard}",
            "shardKey": {"year": year},
            "assignedShard": target_shard,
            "rule": "Range-based partitioning: [Min..1980) -> Shard1 | [1980..2000) -> Shard2 | [2000..Max] -> Shard3"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
