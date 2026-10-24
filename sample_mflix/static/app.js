// Quản lý trạng thái
let currentGenres = [];

document.addEventListener("DOMContentLoaded", () => {
  checkClusterStatus();
  loadMovies();
});

function switchTab(tabName) {
  document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach(el => el.classList.remove("active"));

  if (tabName === "crud") {
    document.querySelector("button[onclick=\"switchTab('crud')\"]").classList.add("active");
    document.getElementById("crudTab").classList.add("active");
  } else {
    document.querySelector("button[onclick=\"switchTab('aggregation')\"]").classList.add("active");
    document.getElementById("aggregationTab").classList.add("active");
    // Chạy mặc định Aggregation 1 nếu chưa chạy
    if (!document.getElementById("pipelineBox").dataset.loaded) {
      runAgg(1);
    }
  }
}

function showToast(msg, isError = false) {
  const toast = document.getElementById("toast");
  toast.textContent = msg;
  toast.style.background = isError ? "var(--danger-text)" : "var(--accent-dark)";
  toast.style.display = "block";
  setTimeout(() => {
    toast.style.display = "none";
  }, 3500);
}

// 1. Kiểm tra Cluster Status
async function checkClusterStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    if (data.status === "connected") {
      document.getElementById("statusText").textContent = 
        `MongoDB Online (${data.counts.movies.toLocaleString()} phim, ${data.counts.comments.toLocaleString()} bình luận)`;
    } else {
      document.getElementById("statusText").textContent = "Lỗi kết nối MongoDB";
      document.querySelector(".status-dot").style.background = "#e74c3c";
    }
  } catch (err) {
    document.getElementById("statusText").textContent = "Không thể kết nối Backend";
    document.querySelector(".status-dot").style.background = "#e74c3c";
  }
}

// 2. Tìm kiếm và Đọc danh sách phim (READ)
async function searchMovies() {
  const q = document.getElementById("searchInput").value;
  const genre = document.getElementById("genreSelect").value;
  loadMovies(q, genre);
}

async function loadMovies(q = "", genre = "") {
  try {
    let url = `/api/movies?limit=12`;
    if (q) url += `&q=${encodeURIComponent(q)}`;
    if (genre) url += `&genre=${encodeURIComponent(genre)}`;

    const res = await fetch(url);
    const data = await res.json();

    document.getElementById("totalCount").textContent = data.total ? data.total.toLocaleString() : 0;

    // Hiển thị câu lệnh MongoDB tương ứng
    const queryBox = document.getElementById("queryExplanation");
    queryBox.style.display = "block";
    queryBox.textContent = `// MongoDB Read Query:\ndb.movies.find(${JSON.stringify(data.query_used)}, {title:1, year:1, genres:1, imdb:1}).sort({year: -1}).limit(12)`;

    // Cập nhật dropdown genres nếu chưa có
    if (currentGenres.length === 0 && data.genres) {
      currentGenres = data.genres;
      const select = document.getElementById("genreSelect");
      data.genres.forEach(g => {
        const opt = document.createElement("option");
        opt.value = g;
        opt.textContent = g;
        select.appendChild(opt);
      });
    }

    // Render danh sách phim
    const grid = document.getElementById("movieGrid");
    grid.innerHTML = "";

    if (!data.movies || data.movies.length === 0) {
      grid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 40px;">Không tìm thấy phim phù hợp</div>`;
      return;
    }

    data.movies.forEach(m => {
      const card = document.createElement("div");
      card.className = "movie-card";

      const rating = m.imdb && m.imdb.rating ? m.imdb.rating : "N/A";
      const genresHtml = (m.genres || []).map(g => `<span class="badge">${g}</span>`).join("");
      const plot = m.plot || "Chưa có tóm tắt nội dung.";

      card.innerHTML = `
        <div>
          <div class="movie-header">
            <h3>${escapeHtml(m.title)}</h3>
          </div>
          <div class="movie-meta">
            <span>📅 ${m.year || "N/A"}</span>
            <span>⭐ IMDb: <strong>${rating}</strong></span>
          </div>
          <div style="margin-bottom: 8px;">${genresHtml}</div>
          <p class="movie-plot">${escapeHtml(plot)}</p>
        </div>
        <div class="movie-actions">
          <button class="btn btn-outline btn-sm" onclick='openEditModal(${JSON.stringify(m).replace(/'/g, "&apos;")})'>Sửa (Update)</button>
          <button class="btn btn-danger btn-sm" onclick="deleteMovie('${m._id}', '${escapeHtml(m.title)}')">Xóa (Delete)</button>
        </div>
      `;
      grid.appendChild(card);
    });

  } catch (err) {
    showToast("Lỗi khi tải danh sách phim", true);
  }
}

// 3. CREATE & UPDATE (Modal)
function openCreateModal() {
  document.getElementById("modalTitle").textContent = "Thêm phim mới (Create - insertOne)";
  document.getElementById("editMovieId").value = "";
  document.getElementById("movieTitleInput").value = "";
  document.getElementById("movieYearInput").value = 2026;
  document.getElementById("movieRatingInput").value = 8.0;
  document.getElementById("movieGenresInput").value = "Drama, Adventure";
  document.getElementById("moviePlotInput").value = "";
  document.getElementById("movieModal").classList.add("active");
}

function openEditModal(movie) {
  document.getElementById("modalTitle").textContent = "Chỉnh sửa phim (Update - updateOne)";
  document.getElementById("editMovieId").value = movie._id;
  document.getElementById("movieTitleInput").value = movie.title || "";
  document.getElementById("movieYearInput").value = movie.year || 2026;
  document.getElementById("movieRatingInput").value = movie.imdb?.rating || 7.0;
  document.getElementById("movieGenresInput").value = (movie.genres || []).join(", ");
  document.getElementById("moviePlotInput").value = movie.plot || "";
  document.getElementById("movieModal").classList.add("active");
}

function closeModal() {
  document.getElementById("movieModal").classList.remove("active");
}

async function saveMovie() {
  const id = document.getElementById("editMovieId").value;
  const title = document.getElementById("movieTitleInput").value.trim();
  const year = parseInt(document.getElementById("movieYearInput").value) || 2026;
  const rating = parseFloat(document.getElementById("movieRatingInput").value) || 7.0;
  const genresStr = document.getElementById("movieGenresInput").value;
  const plot = document.getElementById("moviePlotInput").value.trim();

  if (!title) {
    alert("Vui lòng nhập tiêu đề phim!");
    return;
  }

  const payload = {
    title,
    year,
    rating,
    genres: genresStr.split(",").map(g => g.trim()).filter(Boolean),
    plot
  };

  try {
    let res;
    if (id) {
      // UPDATE
      res = await fetch(`/api/movies/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
    } else {
      // CREATE
      res = await fetch("/api/movies", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
    }

    const data = await res.json();
    if (res.ok) {
      closeModal();
      showToast(data.message || "Thao tác thành công!");
      checkClusterStatus();
      searchMovies();
    } else {
      alert("Lỗi: " + (data.error || "Không thể thực hiện"));
    }
  } catch (err) {
    alert("Lỗi kết nối máy chủ");
  }
}

// 4. DELETE
async function deleteMovie(id, title) {
  if (!confirm(`Bạn có chắc muốn xoá phim "${title}" khỏi MongoDB?`)) {
    return;
  }

  try {
    const res = await fetch(`/api/movies/${id}`, { method: "DELETE" });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message || "Đã xoá phim thành công!");
      checkClusterStatus();
      searchMovies();
    } else {
      alert("Lỗi: " + (data.error || "Không thể xóa"));
    }
  } catch (err) {
    alert("Lỗi mạng khi xóa");
  }
}

// 5. AGGREGATION PIPELINES
async function runAgg(type) {
  document.getElementById("btnAgg1").className = type === 1 ? "btn btn-primary" : "btn btn-outline";
  document.getElementById("btnAgg2").className = type === 2 ? "btn btn-primary" : "btn btn-outline";
  document.getElementById("btnAgg3").className = type === 3 ? "btn btn-primary" : "btn btn-outline";

  const pipelineBox = document.getElementById("pipelineBox");
  const container = document.getElementById("aggResultTableContainer");
  const titleEl = document.getElementById("aggResultTitle");
  
  pipelineBox.textContent = "// Đang thực thi aggregation...";
  container.innerHTML = `<div style="padding: 20px; color: var(--text-muted);">Đang truy vấn MongoDB...</div>`;

  try {
    let url = "";
    if (type === 1) url = "/api/aggregate/genres-stats";
    else if (type === 2) url = "/api/aggregate/top-rated-by-year?min_year=2000";
    else if (type === 3) url = "/api/aggregate/movies-comments-lookup";

    const startTime = performance.now();
    const res = await fetch(url);
    const data = await res.json();
    const duration = ((performance.now() - startTime) / 1000).toFixed(2);

    document.getElementById("aggTime").textContent = `Thời gian thực thi: ${duration}s`;
    pipelineBox.dataset.loaded = "true";
    pipelineBox.textContent = `// MongoDB Aggregation Pipeline:\ndb.movies.aggregate(${JSON.stringify(data.pipeline, null, 2)})`;
    titleEl.textContent = data.title;

    // Render Table
    if (type === 1) {
      renderTable(data.result, [
        { key: "_id", label: "Thể loại (Genre)" },
        { key: "totalMovies", label: "Số lượng phim", format: v => v.toLocaleString() },
        { key: "avgRating", label: "Điểm IMDb TB", format: v => `⭐ ${v}` },
        { key: "maxRating", label: "Điểm cao nhất", format: v => `⭐ ${v}` }
      ]);
    } else if (type === 2) {
      renderTable(data.result, [
        { key: "_id", label: "Năm" },
        { key: "topMovie", label: "Phim xuất sắc nhất năm" },
        { key: "highestRating", label: "Điểm IMDb", format: v => `⭐ ${v}` },
        { key: "votes", label: "Lượt vote", format: v => v?.toLocaleString() },
        { key: "genres", label: "Thể loại", format: v => (v || []).join(", ") }
      ]);
    } else if (type === 3) {
      renderTable(data.result, [
        { key: "title", label: "Tên phim" },
        { key: "year", label: "Năm" },
        { key: "commentCount", label: "Số bình luận (Lookup)", format: v => `💬 ${v}` },
        { key: "latestComment", label: "Bình luận trích dẫn mẫu", format: v => (v && v.length) ? `"${v[0]}"` : "—" }
      ]);
    }
  } catch (err) {
    pipelineBox.textContent = "// Lỗi khi thực thi Aggregation";
    container.innerHTML = `<div style="color: var(--danger-text); padding: 14px;">Lỗi: ${err.message}</div>`;
  }
}

function renderTable(rows, columns) {
  const container = document.getElementById("aggResultTableContainer");
  if (!rows || rows.length === 0) {
    container.innerHTML = `<div style="padding: 16px; color: var(--text-muted);">Không có dữ liệu trả về</div>`;
    return;
  }

  let html = `<table class="data-table"><thead><tr>`;
  columns.forEach(c => html += `<th>${c.label}</th>`);
  html += `</tr></thead><tbody>`;

  rows.forEach(r => {
    html += `<tr>`;
    columns.forEach(c => {
      let val = r[c.key];
      if (c.format) val = c.format(val);
      html += `<td>${val !== undefined && val !== null ? val : "—"}</td>`;
    });
    html += `</tr>`;
  });

  html += `</tbody></table>`;
  container.innerHTML = html;
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
