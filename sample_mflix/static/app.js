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
  } else if (tabName === "aggregation") {
    document.querySelector("button[onclick=\"switchTab('aggregation')\"]").classList.add("active");
    document.getElementById("aggregationTab").classList.add("active");
    // Chạy mặc định Aggregation 1 nếu chưa chạy
    if (!document.getElementById("pipelineBox").dataset.loaded) {
      runAgg(1);
    }
  } else if (tabName === "replication") {
    document.querySelector("button[onclick=\"switchTab('replication')\"]").classList.add("active");
    document.getElementById("replicationTab").classList.add("active");
    loadReplicationStatus();
  } else if (tabName === "sharding") {
    document.querySelector("button[onclick=\"switchTab('sharding')\"]").classList.add("active");
    document.getElementById("shardingTab").classList.add("active");
    loadShardingStatus();
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

// 2. Tìm kiếm và Đọc danh sách phim (READ & TEXT SEARCH)
async function searchMovies() {
  const q = document.getElementById("searchInput").value;
  const genre = document.getElementById("genreSelect").value;
  const mode = document.getElementById("searchModeSelect") ? document.getElementById("searchModeSelect").value : "text";
  loadMovies(q, genre, mode);
}

async function loadMovies(q = "", genre = "", mode = "text") {
  try {
    let url = `/api/movies?limit=12&mode=${encodeURIComponent(mode)}`;
    if (q) url += `&q=${encodeURIComponent(q)}`;
    if (genre) url += `&genre=${encodeURIComponent(genre)}`;

    const res = await fetch(url);
    const data = await res.json();

    document.getElementById("totalCount").textContent = data.total ? data.total.toLocaleString() : 0;

    // Hiển thị câu lệnh MongoDB tương ứng
    const queryBox = document.getElementById("queryExplanation");
    queryBox.style.display = "block";
    queryBox.textContent = `// MongoDB Executed Query:\n${data.mongo_command || JSON.stringify(data.query_used)}`;

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
      grid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 40px;">Không tìm thấy phim phù hợp với từ khóa "${escapeHtml(q)}"</div>`;
      return;
    }

    data.movies.forEach(m => {
      const card = document.createElement("div");
      card.className = "movie-card";

      // Làm sạch hiển thị năm (loại bỏ ký tự lạ như 'è' trong dataset gốc: ví dụ '2010è' -> '2010', '1994è1998' -> '1994 - 1998')
      const displayYear = formatYear(m.year);
      const rating = m.imdb && m.imdb.rating ? m.imdb.rating : "N/A";
      const genresHtml = (m.genres || []).map(g => `<span class="badge">${g}</span>`).join("");
      const plot = m.plot || "Chưa có tóm tắt nội dung.";
      const scoreBadge = m.score ? `<span class="badge" style="background:#e4ece0; color:#2c5b24; font-weight:600;">🎯 TextScore: ${m.score}</span>` : "";

      card.innerHTML = `
        <div>
          <div class="movie-header">
            <h3>${escapeHtml(m.title)}</h3>
          </div>
          <div class="movie-meta">
            <span>📅 ${displayYear}</span>
            <span>⭐ IMDb: <strong>${rating}</strong></span>
            ${scoreBadge}
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
  // Làm sạch năm nếu có ký tự lạ
  const cleanYear = parseInt(String(movie.year || "").replace(/[^\d]/g, "")) || 2026;
  document.getElementById("movieYearInput").value = cleanYear;
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

function formatYear(yearVal) {
  if (!yearVal) return "N/A";
  let s = String(yearVal).trim();
  // Nếu có dạng khoảng năm bị dính 'è' như '1994è1998' -> đổi thành '1994 - 1998'
  if (/^\d{4}è\d{4}$/.test(s)) {
    return s.replace("è", " - ");
  }
  // Loại bỏ ký tự lạ 'è' hoặc các ký tự không phải số ở cuối như '2010è' -> '2010'
  s = s.replace(/è/g, "").replace(/[^\d\s-]/g, "").trim();
  return s || "N/A";
}

// 6. REPLICATION & FAILOVER DEMO LOGIC
async function loadReplicationStatus() {
  const container = document.getElementById("replicationNodesGrid");
  container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 20px;">Đang thăm dò trạng thái các node trong Replica Set...</div>`;

  try {
    const res = await fetch("/api/replication/status");
    const data = await res.json();
    container.innerHTML = "";

    (data.nodes || []).forEach(node => {
      const card = document.createElement("div");
      card.className = "movie-card";

      let statusBadge = "";
      let borderColor = "var(--border-color)";
      let btnActionHtml = "";

      if (node.state === "PRIMARY") {
        statusBadge = `<span class="badge" style="background:#eaf5ea; color:#1e6b22; font-weight:700; font-size:0.85rem;">👑 PRIMARY (Ghi & Đọc)</span>`;
        borderColor = "#9ac596";
        btnActionHtml = `
          <button class="btn btn-danger btn-sm" onclick="toggleNode('${node.container}', 'stop')">
            🛑 Tắt Container
          </button>
        `;
      } else if (node.state === "SECONDARY") {
        statusBadge = `<span class="badge" style="background:#eef2f9; color:#224a86; font-weight:600; font-size:0.85rem;">🔄 SECONDARY (Sao chép)</span>`;
        borderColor = "#b5c7e4";
        btnActionHtml = `
          <button class="btn btn-outline btn-sm" onclick="toggleNode('${node.container}', 'stop')">
            🛑 Tắt Container
          </button>
        `;
      } else {
        statusBadge = `<span class="badge" style="background:#fceeee; color:#a12626; font-weight:700; font-size:0.85rem;">❌ DOWN (Không hoạt động)</span>`;
        borderColor = "#e8b4b4";
        btnActionHtml = `
          <button class="btn btn-primary btn-sm" style="background:#2f6b29;" onclick="toggleNode('${node.container}', 'start')">
            ▶️ Bật lại Container
          </button>
        `;
      }

      card.style.borderColor = borderColor;
      card.innerHTML = `
        <div>
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <h3 style="font-size:1.05rem; font-weight:700;">Node: ${node.name}</h3>
            <span>${statusBadge}</span>
          </div>

          <div style="font-size:0.85rem; color:var(--text-muted); line-height:1.7; margin-bottom:12px;">
            <div><strong>Host Port:</strong> <code>${node.port}</code></div>
            <div><strong>Container:</strong> <code>${node.container}</code></div>
            <div><strong>Độ trễ ping:</strong> ${node.pingMs !== null ? `${node.pingMs} ms` : "N/A"}</div>
            <div><strong>Số tài liệu (Movies):</strong> <strong style="color:var(--accent-dark);">${node.movieCount ? node.movieCount.toLocaleString() : 0}</strong></div>
          </div>
        </div>

        <div class="movie-actions" style="margin-top:auto; padding-top:10px; border-top:1px solid var(--border-color); display:flex; justify-content:flex-end;">
          ${btnActionHtml}
        </div>
      `;

      container.appendChild(card);
    });

  } catch (err) {
    container.innerHTML = `<div style="grid-column: 1/-1; color: var(--danger-text); padding: 20px;">Lỗi kết nối API Replication: ${err.message}</div>`;
  }
}

async function toggleNode(containerName, action) {
  const confirmMsg = action === "stop"
    ? `Bạn có chắc muốn tắt container "${containerName}"? Replica Set sẽ phải tự bầu chọn lại nếu đây là Primary.`
    : `Bật lại container "${containerName}"?`;

  if (!confirm(confirmMsg)) return;

  showToast(`Đang thực hiện docker ${action} ${containerName}...`);
  try {
    const res = await fetch("/api/replication/node-action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ container: containerName, action })
    });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message || "Thao tác thành công!");
      // Chờ 2 giây để MongoDB cập nhật trạng thái bầu chọn
      setTimeout(() => {
        loadReplicationStatus();
        checkClusterStatus();
      }, 2000);
    } else {
      alert("Lỗi: " + (data.error || "Không thể thực thi lệnh docker"));
    }
  } catch (err) {
    alert("Lỗi mạng khi điều khiển container");
  }
}

async function triggerSyncTest() {
  const box = document.getElementById("syncTestResult");
  box.style.display = "block";
  box.textContent = "// Đang ghi 1 document vào Primary và kiểm tra nhân bản trên các node...";

  try {
    const res = await fetch("/api/replication/sync-test", { method: "POST" });
    const data = await res.json();

    if (res.ok) {
      let lines = [
        `✅ ${data.message}`,
        `Document Title: "${data.test_title}"`,
        `Inserted ID: ObjectId("${data.inserted_id}")`,
        `\nKết quả kiểm tra đồng bộ từng Node:`
      ];

      (data.results || []).forEach(r => {
        const icon = r.replicated ? "✅ ĐÃ ĐỒNG BỘ" : "❌ CHƯA CÓ / NODE DOWN";
        lines.push(`  - [${r.node}:${r.port}] (${r.state}) -> ${icon}`);
      });

      box.textContent = lines.join("\n");
      showToast("Đã hoàn tất kiểm tra đồng bộ replication!");
      loadReplicationStatus();
    } else {
      box.textContent = `❌ Lỗi: ${data.error || "Không thể kiểm tra đồng bộ"}`;
    }
  } catch (err) {
    box.textContent = `❌ Lỗi mạng: ${err.message}`;
  }
}

// 7. SHARDING DEMO LOGIC
async function loadShardingStatus() {
  const container = document.getElementById("shardsGrid");
  container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 20px;">Đang tính toán phân bổ dữ liệu trên 3 Shard...</div>`;

  try {
    const res = await fetch("/api/sharding/status");
    const data = await res.json();
    container.innerHTML = "";

    (data.shards || []).forEach((shard, idx) => {
      const card = document.createElement("div");
      card.className = "movie-card";

      // Màu sắc theo từng shard
      const colors = ["#b5c7e4", "#d5ccbe", "#9ac596"];
      card.style.borderColor = colors[idx % colors.length];

      card.innerHTML = `
        <div>
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <h3 style="font-size:1.05rem; font-weight:700;">${shard.name}</h3>
            <span class="badge" style="background:#efece6; font-weight:600;">${shard.percentage}% dữ liệu</span>
          </div>

          <div style="font-size:0.85rem; color:var(--text-muted); line-height:1.7; margin-bottom:12px;">
            <div><strong>Host:</strong> <code>${shard.host}</code></div>
            <div><strong>Khoảng Shard Key:</strong> <code>${shard.keyRange}</code></div>
            <div style="margin-top:4px;"><strong>Mô tả:</strong> ${shard.description}</div>
            <div style="margin-top:6px; font-size:0.95rem;">
              <strong>Số documents:</strong> <strong style="color:var(--accent-dark);">${shard.documentCount.toLocaleString()}</strong> phim
            </div>
          </div>
        </div>

        <!-- Thanh tỷ lệ phân bổ -->
        <div style="background:#e5e2db; height:8px; border-radius:4px; overflow:hidden; margin-top:auto;">
          <div style="background:var(--accent-dark); width:${shard.percentage}%; height:100%;"></div>
        </div>
      `;

      container.appendChild(card);
    });

  } catch (err) {
    container.innerHTML = `<div style="grid-column: 1/-1; color: var(--danger-text); padding: 20px;">Lỗi tải phân bổ Shard: ${err.message}</div>`;
  }
}

async function testRoute(queryType) {
  document.getElementById("btnRouteSingle").className = queryType === "targeted_single" ? "btn btn-primary" : "btn btn-outline";
  document.getElementById("btnRouteRange").className = queryType === "targeted_range" ? "btn btn-primary" : "btn btn-outline";
  document.getElementById("btnRouteScatter").className = queryType === "scatter_gather" ? "btn btn-primary" : "btn btn-outline";

  const box = document.getElementById("routingResultBox");
  box.style.display = "block";
  box.textContent = "// Đang phân tích định tuyến qua mongos router...";

  try {
    const res = await fetch("/api/sharding/route-explain", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query_type: queryType })
    });
    const data = await res.json();

    if (res.ok) {
      const output = [
        `Kiểu truy vấn: ${data.queryType}`,
        `Cú pháp truy vấn mẫu: db.movies.find(${JSON.stringify(data.sampleQuery)})`,
        `\nMongos Router:`,
        `  - Routing: ${data.routingStage}`,
        `  - Shard(s) được gửi truy vấn tới: [ ${data.targetedShards.join(", ")} ]`,
        `  - Đánh giá hiệu năng: ${data.performance}`,
        `\nGiải thích:\n${data.explanation}`
      ];
      box.textContent = output.join("\n");
    } else {
      box.textContent = "Lỗi: " + data.error;
    }
  } catch (err) {
    box.textContent = "Lỗi mạng: " + err.message;
  }
}

async function simulateInsertRoute() {
  const yearInput = document.getElementById("testInsertYear").value;
  const titleInput = document.getElementById("testInsertTitle").value.trim();
  const year = parseInt(yearInput) || 2026;

  const box = document.getElementById("insertRouteResult");
  box.style.display = "block";
  box.textContent = "// Đang tính toán Shard tiếp nhận bản ghi...";

  try {
    const res = await fetch("/api/sharding/insert-route", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ year, title: titleInput || "Sample Movie" })
    });
    const data = await res.json();

    if (res.ok) {
      const output = [
        `${data.message}`,
        `Shard Key giá trị: ${JSON.stringify(data.shardKey)}`,
        `Shard được phân bổ lưu trữ: ${data.assignedShard}`,
        `Nguyên tắc phân vùng: ${data.rule}`
      ];
      box.textContent = output.join("\n");
      showToast(`Bản ghi được gán về ${data.assignedShard}`);
    } else {
      box.textContent = "Lỗi: " + data.error;
    }
  } catch (err) {
    box.textContent = "Lỗi mạng: " + err.message;
  }
}
