import sys
import json
import time
from unittest.mock import patch
import requests

# Import các hàm từ License.py
import License

def mock_check_license(license_key):
    print(f"\n[TEST] Đang giả lập check key: {license_key}")
    time.sleep(1) # Giả lập độ trễ mạng
    
    # Giả lập dữ liệu thành công từ server
    data = {
        "ok": True,
        "license_key": license_key,
        "machine_id": License.make_machine_id(),
        "expires_at": int(time.time()) + 86400 * 30, # Hạn 30 ngày
        "server_ts": int(time.time()),
        "nonce": "test_nonce",
        "ACTIVE": True,
        "features": json.dumps({"name": "Khách hàng Test", "sdt": "0123456789"})
    }
    
    # Tạo chữ ký giả (trong thực tế server sẽ thực hiện việc này)
    return 200, data, 0.5

if __name__ == "__main__":
    print("--- CHƯƠNG TRÌNH TEST HỆ THỐNG BẢN QUYỀN (MOCK) ---")
    
    # Patch hàm _check_license để không gọi ra ngoài internet
    with patch('License._check_license', side_effect=mock_check_license):
        # Chạy app chính của License
        License.main()
