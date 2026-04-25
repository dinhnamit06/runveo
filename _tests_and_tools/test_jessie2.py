import sys
from settings_manager import SettingsManager
import requests

cfg = SettingsManager.load_config()
session_id = cfg.get("TIKTOK_SESSION_ID")

url = "https://api22-normal-c-useast2a.tiktokv.com/media/api/text/speech/invoke/"
headers = {
    "User-Agent": "com.zhiliaoapp.musically/2022600030 (Linux; U; Android 7.1.2; en_US; SM-G988N; Build/NRD90M;tt-ok/3.12.13.1)",
    "Cookie": f"sessionid={session_id.strip()}"
}

payload = {
    "req_text": "Hello, this is a test.",
    "text_speaker": "en_us_002",
    "speaker_map_type": 0,
    "aid": 1180
}

response = requests.post(url, headers=headers, params=payload, timeout=5)
print("RESPONSE:", response.json())
