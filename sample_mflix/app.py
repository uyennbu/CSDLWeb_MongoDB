import os
from datetime import datetime
from bson import ObjectId
from flask import Flask, render_template, request, jsonify
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
        limit = min(int(request.args.get("limit", 10)), 50)
        skip = int(request.args.get("skip", 0))

        filter_query = {}
        if q:
            filter_query["title"] = {"$regex": q, "$options": "i"}
        if genre:
            filter_query["genres"] = genre

        cursor = db.movies.find(
            filter_query,
            {"title": 1, "year": 1, "genres": 1, "imdb": 1, "plot": 1, "poster": 1, "cast": 1}
        ).sort("year", -1).skip(skip).limit(limit)

        movies = list(cursor)
        total = db.movies.count_documents(filter_query)

        # Lấy danh sách thể loại phổ biến để lọc
        genres = db.movies.distinct("genres")
        clean_genres = sorted([g for g in genres if g and isinstance(g, str)])[:25]

        return jsonify({
            "total": total,
            "movies": serialize_doc(movies),
            "genres": clean_genres,
            "query_used": filter_query
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
