// CRUD OPERATION

// Them 1 document phim thu nghiem 
db.movies.insertOne({
  title: "Test Movie 2026",
  year: 2026,
  genres: ["Drama", "Sci-Fi"],
  imdb: { rating: 8.5, votes: 100 },
  is_test_data: true
});

// AGGREGATION