# Patch tiktok_tts_exporter.py
with open('tiktok_tts_exporter.py', 'r', encoding='utf-8') as f:
    content = f.read()

mapping_patch = """    mapping = {
        "tiktok_vn_female_1": "vn_001_female",
        "tiktok_vn_male_1": "vn_002_male",
        "tiktok_vn_female_2": "vn_003_female",
        "tiktok_vn_male_2": "vn_004_male",
        "tiktok_en_us_female": "en_us_001",
        "tiktok_en_us_jessie": "en_us_002",
        "tiktok_en_us_male_1": "en_us_006",
        "tiktok_en_us_male_2": "en_us_010",
        "tiktok_en_uk_male": "en_uk_001",
        "tiktok_en_us_ghostface": "en_us_ghostface",
        "tiktok_en_us_stormtrooper": "en_us_stormtrooper"
    }"""

import re
content = re.sub(r'    mapping = \{.*?\n    \}', mapping_patch, content, flags=re.DOTALL)

with open('tiktok_tts_exporter.py', 'w', encoding='utf-8') as f:
    f.write(content)

# Patch voice_profiles.py
with open('voice_profiles.py', 'r', encoding='utf-8') as f:
    content = f.read()

eng_voices = """
    "tiktok_en_us_female": {
        "label": "Tiktok US Nữ",
        "locale": "en-US",
        "language": "en",
        "gender": "female",
        "style": "tiktok",
        "priority": 106,
        "enabled": True,
        "aliases": ["en-US", "tiktok"],
        "fallback_locales": ["en-GB"],
        "voice_profile": "en_us_001"
    },
    "tiktok_en_us_jessie": {
        "label": "Tiktok Jessie (US)",
        "locale": "en-US",
        "language": "en",
        "gender": "female",
        "style": "tiktok",
        "priority": 105,
        "enabled": True,
        "aliases": ["en-US", "tiktok"],
        "fallback_locales": ["en-GB"],
        "voice_profile": "en_us_002"
    },
    "tiktok_en_us_male_1": {
        "label": "Tiktok US Nam Trẻ",
        "locale": "en-US",
        "language": "en",
        "gender": "male",
        "style": "tiktok",
        "priority": 104,
        "enabled": True,
        "aliases": ["en-US", "tiktok"],
        "fallback_locales": ["en-GB"],
        "voice_profile": "en_us_006"
    },
    "tiktok_en_us_male_2": {
        "label": "Tiktok US Nam Trầm",
        "locale": "en-US",
        "language": "en",
        "gender": "male",
        "style": "tiktok",
        "priority": 103,
        "enabled": True,
        "aliases": ["en-US", "tiktok"],
        "fallback_locales": ["en-GB"],
        "voice_profile": "en_us_010"
    },
    "tiktok_en_uk_male": {
        "label": "Tiktok UK Nam Trang trọng",
        "locale": "en-GB",
        "language": "en",
        "gender": "male",
        "style": "tiktok",
        "priority": 102,
        "enabled": True,
        "aliases": ["en-GB", "tiktok"],
        "fallback_locales": ["en-US"],
        "voice_profile": "en_uk_001"
    },
    "tiktok_en_us_ghostface": {
        "label": "Tiktok Giọng Ma Quỷ (Ghostface)",
        "locale": "en-US",
        "language": "en",
        "gender": "male",
        "style": "tiktok",
        "priority": 101,
        "enabled": True,
        "aliases": ["en-US", "tiktok"],
        "fallback_locales": ["en-GB"],
        "voice_profile": "en_us_ghostface"
    },
    "tiktok_en_us_stormtrooper": {
        "label": "Tiktok Star Wars (Stormtrooper)",
        "locale": "en-US",
        "language": "en",
        "gender": "male",
        "style": "tiktok",
        "priority": 100,
        "enabled": True,
        "aliases": ["en-US", "tiktok"],
        "fallback_locales": ["en-GB"],
        "voice_profile": "en_us_stormtrooper"
    },"""

if '"tiktok_en_us_female"' not in content:
    content = content.replace('"Nam_Kechuyen": {', eng_voices + '\n    "Nam_Kechuyen": {')

with open('voice_profiles.py', 'w', encoding='utf-8') as f:
    f.write(content)

import shutil
try:
    shutil.copy('voice_profiles.py', r'dist\VEO_4.0_V2.2.6_PROMAX\_internal\voice_profiles.py')
    shutil.copy('tiktok_tts_exporter.py', r'dist\VEO_4.0_V2.2.6_PROMAX\_internal\tiktok_tts_exporter.py')
except Exception:
    pass

print("Added English TikTok voices!")
