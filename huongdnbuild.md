# HƯỚNG DẪN BUILD VÀ UPDATE VEO 4.0 (A-Z)

Đây là quy trình chuẩn để bạn phát hành phần mềm một cách chuyên nghiệp và bảo mật.

## 1. Chuẩn bị (Trước khi Build)
- Chỉnh sửa code tính năng trong các file `.py`.
- Cập nhật phiên bản hoặc tên Brand trong `branding_config.py`.

## 2. Mã hóa bảo vệ Code 🛡️
- Chạy file: `bao_mat_code.bat`.
- File này sẽ dùng PyArmor để mã hóa toàn bộ code của bạn vào thư mục `dist_obfuscated`.
- **Lưu ý**: Nếu chưa cài PyArmor, file .bat sẽ tự động cài cho bạn.

## 3. Đóng gói EXE 📦
- Mở Terminal và chạy lệnh:
  ```powershell
  python build_obfuscated_exe.py
  ```
- File EXE chính thức sẽ nằm trong thư mục: `dist/VEO_4_0_V2.2.6_PROTECTED`.

## 4. Quản lý Khách hàng 🔑
- **Cấp Key mới**: Vào Google Sheet, thêm 1 dòng mới với mã license_key tự chọn.
- **Để Machine ID trống**: Khi khách nhập Key lần đầu trên máy họ, hệ thống sẽ tự động bắt mã máy và khóa Key đó lại.
- **Mở khóa máy**: Nếu khách muốn đổi máy, bạn chỉ cần vào Sheet xóa mã cũ ở cột `machine_id` là xong.

## 5. Quy trình Update
- Khi có bản mới, bạn chỉ cần thực hiện lại từ Bước 1 đến Bước 3.
- Gửi file EXE mới cho khách. Khách không cần nhập lại Key cũ (vì máy đã được nhận diện).

---
*Chúc bạn thành công với dự án VEO 4.0!*
