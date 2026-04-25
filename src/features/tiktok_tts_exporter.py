# -*- coding: utf-8 -*-
from __future__ import annotations

import requests
import base64


def get_tiktok_voice_id(voice_profile: str) -> str:
    # Match the voice profile id from voice_profiles.py to the actual Tiktok voice ID
    mapping = {
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
    }
    return mapping.get(voice_profile, "vn_001_female")


def _split_tts_text(text: str, limit: int = 280) -> list[str]:
    clean = " ".join(str(text or "").split())
    if len(clean) <= limit:
        return [clean] if clean else []

    chunks: list[str] = []
    current = ""
    for sentence in clean.replace("!", "!.").replace("?", "?.").split("."):
        part = sentence.strip()
        if not part:
            continue
        if current and len(current) + len(part) + 2 <= limit:
            current = f"{current}. {part}"
            continue
        if current:
            chunks.append(current.strip())
        while len(part) > limit:
            cut = part.rfind(" ", 0, limit)
            if cut < 80:
                cut = limit
            chunks.append(part[:cut].strip())
            part = part[cut:].strip()
        current = part
    if current:
        chunks.append(current.strip())
    return [chunk for chunk in chunks if chunk]


def _request_tiktok_audio(text: str, voice_id: str, session_id: str) -> bytes | None:
    url = "https://api16-normal-v6.tiktokv.com/media/api/text/speech/invoke/"
    headers = {
        "User-Agent": "com.zhiliaoapp.musically/2022600030 (Linux; U; Android 7.1.2; en_US; SM-G988N; Build/NRD90M;tt-ok/3.12.13.1)",
        "Cookie": f"sessionid={session_id.strip()}",
    }
    payload = {
        "req_text": text.strip(),
        "text_speaker": voice_id,
        "speaker_map_type": 0,
        "aid": 1233,
    }
    response = requests.post(url, headers=headers, params=payload, timeout=30)
    data = response.json()
    if data.get("status_code") == 0 and data.get("data") and data["data"].get("v_str"):
        return base64.b64decode(data["data"]["v_str"])
    print(f"Tiktok TTS API Loi: {data.get('message')}".encode("ascii", "ignore").decode("ascii"))
    return None


def tiktok_tts_save(text: str, out_path: str, voice_profile: str, session_id: str) -> bool:
    if not text.strip():
        return False
        
    if not session_id or not session_id.strip():
        print(f"Loi TTS: Thieu TikTok sessionid de tao giong {voice_profile}".encode("ascii", "ignore").decode("ascii"))
        return False

    voice_id = get_tiktok_voice_id(voice_profile)
    
    try:
        chunks = _split_tts_text(text)
        audio_parts: list[bytes] = []
        for chunk in chunks:
            audio_bytes = _request_tiktok_audio(chunk, voice_id, session_id)
            if not audio_bytes:
                return False
            audio_parts.append(audio_bytes)
        if not audio_parts:
            return False
        with open(out_path, "wb") as f:
            for audio_bytes in audio_parts:
                f.write(audio_bytes)
        return True
    except Exception as e:
        print(f"Loi goi Tiktok TTS API: {e}".encode("ascii", "ignore").decode("ascii"))
        return False

if __name__ == "__main__":
    # Test
    ok = tiktok_tts_save("Xin chào, đây là giọng thử nghiệm của TikTok", "test_tiktok.mp3", "tiktok_vn_female_1", "YOUR_SESSION_ID_HERE")
    print(f"Success: {ok}")
