// ############ INDEXING
// 1. Tạo, Xóa, Xem
// Tạo index
db.movies.createIndex(
    {year: 1}
);
// Xóa 1 index
db.movies.dropIndex(
    {year: 1}
);
// Xóa toàn bộ các index
db.movies.dropIndexes()
// Xem các index hiện có
db.movies.getIndexes();

// 2. So sánh hiệu năng
// Xem kế hoạch thực thi truy vấn trước khi tạo index
db.movies.find({ year: { $lt: 2000 } }).explain("executionStats");
// Tạo index
db.movies.createIndex({ year: 1 });
// Xem lại kế hoạch thực thi, so sánh sự thay đổi
db.movies.find({ year: { $lt: 2000 } }).explain("executionStats");

// ############ TEXT SEARCH
// 1. Tạo text index
db.movies.createIndex (
    {
        title : "text", // Các trường được sử dụng trong index
        plot : "text",
        fullplot : "text"
    },
    {
        weights :{ // Trọng số tính điểm
            title : 10,
            plot : 3,
            fullplot : 1
        },
        name : "MovieFullTextIndex",
        default_language : "english" // Ngôn ngữ mặc định để thực hiện loại bỏ stop world và stemming
    }
);
// 2. Tìm kiếm theo từ khóa
db.movies.find(
    {$text : {$search : "train robbery bandits"}}, // Điều kiện tìm kiếm
    { // projection
        title : 1,
        plot : 1,
        year : 1,
        score : { $meta : "textScore" } ,
        _id : 0
    }).sort({score : { $meta : "textScore"}}).limit(5);
// 3. Tìm kiếm theo từ chính xác
db.movies.find(
    {$text: {$search: "\"bank robbers\""}},
    {
        title : 1,
        plot : 1,
        _id : 0
    }
);

// 4. Tìm kiếm loại trừ từ khóa
db.movies.find(
    {$text: {$search: "train -cowboy"}},
    {
        title : 1,
        plot : 1,
        _id : 0
    }
);