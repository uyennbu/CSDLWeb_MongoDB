/**
 * demo.js - Script khởi tạo và minh họa cụm Replica Set rs0 gồm 3 nodes:
 *   - mongo1 (port 27017, priority 2 - ưu tiên làm Primary)
 *   - mongo2 (port 27018, priority 1 - Secondary)
 *   - mongo3 (port 27019, priority 1 - Secondary)
 */

print("\n==============================================================");
print(" [BƯỚC 1] KIỂM TRA & KHỞI TẠO CỤM REPLICA SET (rs0)");
print("==============================================================");

var isInitialized = false;
try {
  var status = rs.status();
  if (status.ok === 1) {
    print(">> Replica set 'rs0' đã được khởi tạo trước đó. Trạng thái: OK");
    isInitialized = true;
  }
} catch (e) {
  print(">> Replica set chưa khởi tạo. Bắt đầu gọi rs.initiate()...");
}

if (!isInitialized) {
  var config = {
    _id: "rs0",
    members: [
      { _id: 0, host: "mongo1:27017", priority: 2 },
      { _id: 1, host: "mongo2:27018", priority: 1 },
      { _id: 2, host: "mongo3:27019", priority: 1 }
    ]
  };

  var initResult = rs.initiate(config);
  print(">> Kết quả rs.initiate():");
  printjson(initResult);
}

// Chờ cụm bầu chọn PRIMARY thành công
print("\n>> Đang chờ cụm bầu chọn PRIMARY hoàn tất (tối đa 30s)...");
var primaryReady = false;
for (var i = 0; i < 30; i++) {
  try {
    var hello = db.hello();
    if (hello.isWritablePrimary) {
      print(">> THÀNH CÔNG: Đã có PRIMARY node (" + hello.me + ")");
      primaryReady = true;
      break;
    }
  } catch (err) {}
  sleep(1000);
}

if (!primaryReady) {
  print(">> [LƯU Ý]: Hệ thống vẫn đang đồng bộ hoặc đang bầu chọn. Vui lòng kiểm tra lại bằng lệnh rs.status().");
}

print("\n==============================================================");
print(" [BƯỚC 2] TRẠNG THÁI CÁC THÀNH VIÊN TRONG CLUSTER");
print("==============================================================");
var currentStatus = rs.status();
if (currentStatus && currentStatus.members) {
  currentStatus.members.forEach(function(member) {
    var stateDesc = member.stateStr;
    if (member.state === 1) {
      stateDesc += " (Ghi dữ liệu chính / Primary)";
    } else if (member.state === 2) {
      stateDesc += " (Sao chép dữ liệu / Secondary)";
    }
    print(" * Node [" + member.name + "]: " + stateDesc + " | Health: " + member.health + " | Uptime: " + member.uptime + "s");
  });
}

print("\n==============================================================");
print(" [BƯỚC 3] NHẬP DỮ LIỆU TỪ FILE products.json VÀO PRIMARY");
print("==============================================================");
var demoDb = db.getSiblingDB("shop_online_db");
var fs = require("fs");

var possiblePaths = [
  "/scripts/products.json",
  "./products.json",
  "products.json",
  "./2_cluster/products.json"
];

var jsonPath = possiblePaths.find(function(p) {
  return fs.existsSync(p);
});

if (jsonPath) {
  var fileData = fs.readFileSync(jsonPath, "utf-8");
  var products = EJSON.parse(fileData);

  // Làm mới collection và nạp dữ liệu từ products.json
  demoDb.products.drop();
  var insertRes = demoDb.products.insertMany(products);
  print(">> Đã nhập thành công " + Object.keys(insertRes.insertedIds).length + " sản phẩm từ: " + jsonPath);
  print(">> Tổng số tài liệu hiện có trong 'shop_online_db.products': " + demoDb.products.countDocuments());
} else {
  print(">> [CẢNH BÁO]: Không tìm thấy file products.json tại các đường dẫn mặc định.");
}

print("\n==============================================================");
print(" CỤM REPLICA SET ĐÃ SẴN SÀNG HOẠT ĐỘNG!");
print("==============================================================\n");