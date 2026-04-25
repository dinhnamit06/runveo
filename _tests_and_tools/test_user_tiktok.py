import sys
import os

from settings_manager import SettingsManager
from tiktok_tts_exporter import tiktok_tts_save

def main():
    cfg = SettingsManager.load_config()
    session_id = cfg.get("TIKTOK_SESSION_ID") or cfg.get("tiktok_session_id")
    
    if not session_id:
        print("Lỗi: Chưa tìm thấy TIKTOK_SESSION_ID trong config.json")
        sys.exit(1)
        
    print(f"Đã tìm thấy Session ID: {session_id[:10]}...")
    
    text = "Xin chào, đây là bài test tự động từ hệ thống để kiểm tra giọng đọc Capcut."
    out_file = "test_capcut_audio.mp3"
    
    print(f"Đang gọi API Tiktok TTS cho đoạn text: '{text}'...")
    
    success = tiktok_tts_save(text, out_file, "tiktok_vn_female_1", session_id)
    
    if success:
        if os.path.exists(out_file) and os.path.getsize(out_file) > 0:
            print(f"THÀNH CÔNG! Đã tạo file: {out_file} ({os.path.getsize(out_file)} bytes)")
        else:
            print("LỖI: API báo thành công nhưng file audio trống hoặc không được tạo!")
    else:
        print("LỖI: tiktok_tts_save trả về False!")

if __name__ == "__main__":
    main()
