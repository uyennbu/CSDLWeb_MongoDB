import os
import re
import json
import socket
from datetime import datetime
from bson import ObjectId
from flask import Flask, render_template, request, jsonify
import pymongo
from pymongo import MongoClient

# Tự động ánh xạ hostname của các node Replica Set sang 127.0.0.1
# Giúp PyMongo kết nối cụm Replica Set từ máy host (ngoài Docker)
# mà không bắt buộc người dùng phải sửa file /etc/hosts bằng quyền sudo.
_orig_getaddrinfo = socket.getaddrinfo
def _custom_getaddrinfo(host, port, *args, **kwargs):
    if host in ("mflix1", "mflix2", "mflix3"):
        host = "127.0.0.1"
    return _orig_getaddrinfo(host, port, *args, **kwargs)
socket.getaddrinfo = _custom_getaddrinfo

app = Flask(__name__)

# Cấu hình 3 node trong cụm
NODES_CONFIG = [
    {"name": "mflix1", "port": 27030, "container": "mflix1"},
    {"name": "mflix2", "port": 27031, "container": "mflix2"},
    {"name": "mflix3", "port": 27032, "container": "mflix3"}
]

# Chuỗi kết nối Replica Set chứa cả 3 node và chỉ định readPreference=primaryPreferred
# Khi Primary sập, PyMongo sẽ tự động đọc từ Secondary còn lại mà không làm gián đoạn web
MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb://localhost:27030,localhost:27031,localhost:27032/sample_mflix?replicaSet=rsMflix&readPreference=primaryPreferred"
)

client = None
_cached_db = None

def get_fallback_db():
    """Fallback: Quét tìm trực tiếp (directConnection) một node bất kỳ còn sống trong cụm"""
    for cfg in NODES_CONFIG:
        try:
            c = MongoClient(
                f"mongodb://localhost:{cfg['port']}/?directConnection=true",
                serverSelectionTimeoutMS=800,
                connectTimeoutMS=800
            )
            c.admin.command('ping')
            return c.get_database("sample_mflix", read_preference=pymongo.read_preferences.ReadPreference.SECONDARY_PREFERRED)
        except Exception:
            continue
    return None

def get_db():
    """
    Lấy kết nối database:
    1. Ưu tiên Replica Set client (hỗ trợ tự động failover sang PRIMARY mới hoặc đọc từ SECONDARY).
    2. Nếu Replica Set chưa sẵn sàng hoặc lỗi, fallback kết nối trực tiếp tới node còn sống.
    """
    global client, _cached_db
    if client is None:
        try:
            client = MongoClient(
                MONGO_URI,
                serverSelectionTimeoutMS=2000,
                connectTimeoutMS=2000,
                retryWrites=True
            )
            _cached_db = client.get_database("sample_mflix", read_preference=pymongo.read_preferences.ReadPreference.PRIMARY_PREFERRED)
        except Exception as e:
            print(f"Không thể khởi tạo MongoClient Replica Set: {e}")
            client = None
            _cached_db = None

    if _cached_db is not None:
        return _cached_db

    return get_fallback_db()

class CollectionProxy:
    """Proxy bọc từng collection, tự động chuyển hướng truy vấn sang node còn sống nếu kết nối gặp lỗi"""
    def __init__(self, collection_name):
        self._name = collection_name

    def _get_coll(self):
        target = get_db()
        if target is None:
            raise pymongo.errors.ConnectionFailure("Không thể kết nối tới bất kỳ node MongoDB nào trong cụm!")
        return getattr(target, self._name)

    def __getattr__(self, name):
        attr = getattr(self._get_coll(), name)
        if callable(attr):
            def wrapper(*args, **kwargs):
                try:
                    return attr(*args, **kwargs)
                except (pymongo.errors.AutoReconnect, pymongo.errors.ServerSelectionTimeoutError, pymongo.errors.ConnectionFailure):
                    # Nếu node hiện tại sập hoặc đang bầu cử, tự động truy vấn sang node còn sống
                    fallback = get_fallback_db()
                    if fallback is not None:
                        fb_attr = getattr(getattr(fallback, self._name), name)
                        return fb_attr(*args, **kwargs)
                    raise
            return wrapper
        return attr

class DatabaseProxy:
    """Proxy cho biến 'db' để toàn bộ app gọi db.movies, db.comments... luôn lấy kết nối còn sống"""
    def __getattr__(self, name):
        return CollectionProxy(name)

    def __getitem__(self, name):
        return CollectionProxy(name)

    def __bool__(self):
        try:
            return get_db() is not None
        except Exception:
            return False

db = DatabaseProxy()

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
            elif k == "year" and isinstance(v, str):
                # Làm sạch dữ liệu năm bị dính ký tự lạ trong sample data (ví dụ '2010è' -> 2010)
                cleaned = v.replace("è", " ").strip()
                digits = "".join([c for c in cleaned if c.isdigit()])
                new_doc[k] = int(digits[:4]) if len(digits) >= 4 else v
            elif isinstance(v, (dict, list)):
                new_doc[k] = serialize_doc(v)
            else:
                new_doc[k] = v
        return new_doc
    return doc

def to_shell(value):
    """Chuyển dict/list Python sang cú pháp mongosh dễ đọc, ví dụ: { $text: { $search: "abc" } }"""
    if isinstance(value, dict):
        if not value:
            return "{}"
        parts = []
        for k, v in value.items():
            key = k if re.fullmatch(r"[A-Za-z_$][\w$]*", k) else json.dumps(k)
            parts.append(f"{key}: {to_shell(v)}")
        return "{ " + ", ".join(parts) + " }"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(to_shell(v) for v in value) + "]"
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return str(value)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status", methods=["GET"])
def get_status():
    """Kiểm tra trạng thái cluster và đếm số lượng tài liệu"""
    if get_db() is None:
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

        # Mô tả câu lệnh MongoDB (sinh trực tiếp từ filter/projection/sort thật đã dùng ở trên)
        sort_doc = {field: direction for field, direction in sort_criteria}
        mongo_code = (
            f"db.movies.find(\n"
            f"  {to_shell(filter_query)},\n"
            f"  {to_shell(projection)}\n"
            f").sort({to_shell(sort_doc)})"
            + (f".skip({skip})" if skip else "")
            + f".limit({limit})"
            + f"\n\n// Đếm tổng số kết quả:\ndb.movies.countDocuments({to_shell(filter_query)})"
        )

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
                    # Một số phim có imdb.rating = "" (chuỗi rỗng). Theo thứ tự so sánh BSON,
                    # string > number nên $max sẽ trả về "" -> chỉ lấy giá trị kiểu số.
                    "maxRating": {
                        "$max": {
                            "$cond": [{"$isNumber": "$imdb.rating"}, "$imdb.rating", None]
                        }
                    }
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

# @app.route("/api/aggregate/movies-comments-lookup", methods=["GET"])
# def agg_movies_lookup():
    # """
    # Aggregation 3: $lookup (JOIN) nối bảng movies với comments
    # Lấy danh sách các phim có nhiều bình luận nhất
    # """
    # try:
        # pipeline = [
            # {
                # "$lookup": {
                    # "from": "comments",
                    # "localField": "_id",
                    # "foreignField": "movie_id",
                    # "as": "movie_comments"
                # }
            # },
            # {
                # "$project": {
                    # "title": 1,
                    # "year": 1,
                    # "genres": 1,
                    # "commentCount": {"$size": "$movie_comments"},
                    # "latestComment": {
                        # "$slice": ["$movie_comments.text", 2]
                    # }
                # }
            # },
            # {"$sort": {"commentCount": -1}},
            # {"$limit": 8}
        # ]

        # result = list(db.movies.aggregate(pipeline))
        # return jsonify({
            # "title": "Lookup (JOIN): Phim có nhiều bình luận nhất từ collection 'comments'",
            # "pipeline": pipeline,
            # "result": serialize_doc(result)
        # })
    # except Exception as e:
        # return jsonify({"error": str(e)}), 500

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
