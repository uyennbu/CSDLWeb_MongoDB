import requests

# Endpoint API cho dataset Civil Service List Active
url = "https://data.cityofnewyork.us/resource/vx8i-nprf.json"

# Thêm header User-Agent để tránh bị nhận diện là bot đơn thuần
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

response = requests.get(url, headers=headers)

# Kiểm tra mã trạng thái HTTP (status code)
print(f"Status Code: {response.status_code}")

# In ra nội dung thô (raw text) mà server thực sự trả về
print("Response Text:", response.text)

# Sau đó mới tiến hành ép kiểu JSON nếu hợp lệ
try:
    data = response.json()
    print("Dữ liệu JSON:", data)
except requests.exceptions.JSONDecodeError:
    print("Lỗi: Server không trả về định dạng JSON hợp lệ!")