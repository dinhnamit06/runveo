# Patch tiktok_tts_exporter.py endpoint
with open('tiktok_tts_exporter.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix URL
content = content.replace(
    'url = "https://api22-normal-c-useast2a.tiktokv.com/media/api/text/speech/invoke/"',
    'url = "https://api16-normal-v6.tiktokv.com/media/api/text/speech/invoke/"'
)

# Fix print statements to avoid UnicodeEncodeError on Windows
content = content.replace(
    'print(f"Lỗi TTS: Thiếu TikTok sessionid để tạo giọng {voice_profile}")',
    'print(f"Loi TTS: Thieu TikTok sessionid de tao giong {voice_profile}".encode("ascii", "ignore").decode("ascii"))'
)
content = content.replace(
    'print(f"Tiktok TTS API Lỗi: {data.get(\'message\')}")',
    'print(f"Tiktok TTS API Loi: {data.get(\'message\')}".encode("ascii", "ignore").decode("ascii"))'
)
content = content.replace(
    'print(f"Lỗi gọi Tiktok TTS API: {e}")',
    'print(f"Loi goi Tiktok TTS API: {e}".encode("ascii", "ignore").decode("ascii"))'
)

with open('tiktok_tts_exporter.py', 'w', encoding='utf-8') as f:
    f.write(content)

import shutil
try:
    shutil.copy('tiktok_tts_exporter.py', r'dist\VEO_4.0_V2.2.6_PROMAX\_internal\tiktok_tts_exporter.py')
except Exception:
    pass

print("Patched tiktok url!")
