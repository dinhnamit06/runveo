# Patch tts_voices.py
with open('tts_voices.py', 'r', encoding='utf-8') as f:
    content = f.read()

tiktok_voices_tts = """    {"key": "ko-KR-InJoonNeural", "label": "InJoon (Nam)", "locale": "ko-KR", "gender": "male"},
    {"key": "tiktok_vn_female_1", "label": "Tiktok Nữ miền Nam", "locale": "vi-VN", "gender": "female"},
    {"key": "tiktok_vn_male_1", "label": "Tiktok Nam miền Nam", "locale": "vi-VN", "gender": "male"},
    {"key": "tiktok_vn_female_2", "label": "Tiktok Nữ miền Bắc", "locale": "vi-VN", "gender": "female"},
    {"key": "tiktok_vn_male_2", "label": "Tiktok Nam miền Bắc", "locale": "vi-VN", "gender": "male"},
    {"key": "tiktok_en_us_female", "label": "Tiktok US Nữ", "locale": "en-US", "gender": "female"},
    {"key": "tiktok_en_us_jessie", "label": "Tiktok Jessie (US)", "locale": "en-US", "gender": "female"},
    {"key": "tiktok_en_us_male_1", "label": "Tiktok US Nam Trẻ", "locale": "en-US", "gender": "male"},
    {"key": "tiktok_en_us_male_2", "label": "Tiktok US Nam Trầm", "locale": "en-US", "gender": "male"},
    {"key": "tiktok_en_uk_male", "label": "Tiktok UK Nam Trang trọng", "locale": "en-GB", "gender": "male"},
    {"key": "tiktok_en_us_ghostface", "label": "Tiktok Giọng Ma Quỷ (Ghostface)", "locale": "en-US", "gender": "male"},
    {"key": "tiktok_en_us_stormtrooper", "label": "Tiktok Star Wars (Stormtrooper)", "locale": "en-US", "gender": "male"},"""

if '"tiktok_vn_female_1"' not in content:
    content = content.replace('    {"key": "ko-KR-InJoonNeural", "label": "InJoon (Nam)", "locale": "ko-KR", "gender": "male"},', tiktok_voices_tts)

with open('tts_voices.py', 'w', encoding='utf-8') as f:
    f.write(content)

import shutil
try:
    shutil.copy('tts_voices.py', r'dist\VEO_4.0_V2.2.6_PROMAX\_internal\tts_voices.py')
except Exception:
    pass

print("Added TikTok voices to tts_voices.py")
