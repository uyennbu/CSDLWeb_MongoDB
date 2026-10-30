// CRUD OPERATION

// Tạo mới (Create/Insert)

// Them 1 document phim thu nghiem 
db.movies.insertOne({
  title: "Test Movie 2026",
  year: 2026,
  genres: ["Drama", "Sci-Fi"],
  imdb: { rating: 8.5, votes: 100 },
  is_test_data: true
});

// Them nhieu document dong thoi 
db.movies.insertMany([
  { title: "Test Movie Action", year: 2026, genres: ["Action"], is_test_data: true },
  { title: "Test Movie Comedy", year: 2026, genres: ["Comedy"], is_test_data: true }
]);

// Đọc (Read/Query)

// Tim cac bo phim ra mat sau nam 2010 va thuoc the loai "Drama" (chi lay thuoc tinh title, year va imdb.rating)
db.movies.find(
    { year: { $gt: 2010 }, genres: "Drama" },
    { title: 1, year: 1, "imdb.rating": 1, _id: 0 } );

// Sửa (Update)

// Operator Update: Cap nhat chinh xac truong du lieu bang $set, $inc
db.movies.updateOne(
  { title: "Test Movie 2026" },
  {
    $set: { "imdb.rating": 9.0 },
    $inc: { "imdb.votes": 1 }
  },
  { upsert: true } // Tao moi neu khong tim thay 
);

// Thao tac nguyen tu findAndModify (find_one_and_update) tren collection comments
db.comments.findAndModify({
  query: { movie_id: ObjectId('573a1390f29313caabcd4323'), name: "Mercedes Tyler" },
  update: { $set: { text: "Noi dung binh luan da duoc cap nhat." } },
  new: true
});

// Xóa (Delete)

// Xoa 1 document thoa man dieu kien 
db.movies.deleteOne({ title: "Test Movie 2026" });

// Xoa tat ca document thu nghiem de dua dataset ve trang thai ban dau 
db.movies.deleteMany({ is_test_data: true });

// Xoa toan bo Collection va xoa sach cac Index lien quan (chi dung cho collection tam/thu nghiem) 
db.temp_test_collection.drop();

// AGGREGATION
db.movies.aggregate([
  // Buoc 1: Loc cac bo phim duoc phat hanh tu nam 2000 tro lai day
  { $match: { 
      released: { $gte: ISODate("2000-01-01T00:00:00Z") } 
  }},
  
  // Buoc 2: Nhom theo Nam va Thang phat hanh, tinh tong luot vote IMDb va dem so phim
  { $group: {
      _id: {
        year: { $year: "$released" },
        month: { $month: "$released" }
      },
      total_imdb_votes: { $sum: "$imdb.votes" },
      movie_count: { $sum: 1 }
  }},
  
  // Buoc 3: Sap xep giam dan theo thoi gian (Nam va Thang)
  { $sort: { "_id.year": -1, "_id.month": -1 } },
    
  // Buoc 4: Luu ket qua vao collection moi
  { $out: "monthly_movies_summary" }
]);





// Them nhieu document dong thoi 
db.movies.insertMany([
  { title: "Test Movie Action", year: 2026, genres: ["Action"], is_test_data: true },
  { title: "Test Movie Comedy", year: 2026, genres: ["Comedy"], is_test_data: true }
]);

// Tim cac document thu nghiem vua them 
db.movies.find({is_test_data: true})

// Cập nhật nhiều document cùng lúc thỏa mãn điều kiện
db.movies.updateMany(
  { is_test_data: true }, // Lọc tất cả các phim thử nghiệm
  {
    $set: { "status": "Reviewed" }, // Thêm/Cập nhật trường status
    $inc: { "imdb.votes": 10 }      // Tăng lượt vote của tất cả lên 10
  }
);

// Xoa tat ca document thu nghiem 
db.movies.deleteMany({ is_test_data: true });

// AGGREGATION
db.movies.aggregate([
  // Buoc 1: Loc cac bo phim duoc phat hanh tu nam 2000 tro lai day
  { $match: { 
      released: { $gte: ISODate("2000-01-01T00:00:00Z") } 
  }},
  
  // Buoc 2: Nhom theo Nam va Thang phat hanh, tinh tong luot vote IMDb va dem so phim
  { $group: {
      _id: {
        year: { $year: "$released" },
        month: { $month: "$released" }
      },
      total_imdb_votes: { $sum: "$imdb.votes" },
      movie_count: { $sum: 1 }
  }},
  
  // Buoc 3: Sap xep giam dan theo thoi gian (Nam va Thang)
  { $sort: { "_id.year": -1, "_id.month": -1 } },
    
  // Buoc 4: Luu ket qua vao collection moi
  { $out: "monthly_movies_summary" }
]);