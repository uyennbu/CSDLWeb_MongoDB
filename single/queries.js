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