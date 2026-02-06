"""
Convert service-account-key.json to Base64
Chạy file này để lấy chuỗi base64, copy và paste vào Railway Dashboard
"""

import base64
import os

# File path
json_file = "service-account-key.json"

if not os.path.exists(json_file):
    print(f"❌ Không tìm thấy file: {json_file}")
    exit(1)

# Read and encode to base64
with open(json_file, 'rb') as f:
    content = f.read()

base64_string = base64.b64encode(content).decode('utf-8')

# Print result
print("=" * 60)
print("✅ ĐÃ CHUYỂN ĐỔI THÀNH CÔNG!")
print("=" * 60)
print("\n📋 Copy chuỗi base64 bên dưới:\n")
print(base64_string)
print("\n" + "=" * 60)
print("\n📌 HƯỚNG DẪN:")
print("1. Copy toàn bộ chuỗi trên")
print("2. Vào Railway Dashboard: https://railway.app")
print("3. Chọn project GMV → Variables")
print("4. Thêm biến: GOOGLE_SERVICE_ACCOUNT_JSON")
print("5. Paste chuỗi base64 vào value")
print("6. Save → Railway sẽ tự redeploy")
print("=" * 60)

# Also save to file for easy copy
output_file = "base64_output.txt"
with open(output_file, 'w') as f:
    f.write(base64_string)
print(f"\n💾 Đã lưu vào file: {output_file}")
