import requests
import base64
from settings_manager import SettingsManager

def test_tiktok(endpoint):
    cfg = SettingsManager.load_config()
    session_id = cfg.get("TIKTOK_SESSION_ID") or cfg.get("tiktok_session_id")
    
    url = f"https://{endpoint}/media/api/text/speech/invoke/"
    headers = {
        "User-Agent": "com.zhiliaoapp.musically/2022600030 (Linux; U; Android 7.1.2; en_US; SM-G988N; Build/NRD90M;tt-ok/3.12.13.1)",
        "Cookie": f"sessionid={session_id.strip()}"
    }
    payload = {
        "req_text": "Chào bạn, đây là test.",
        "text_speaker": "vn_001_female",
        "speaker_map_type": 0,
        "aid": 1180
    }
    print(f"Testing {endpoint}...")
    try:
        response = requests.post(url, headers=headers, params=payload, timeout=10)
        data = response.json()
        if data.get("status_code") == 0 and data.get("data") and data["data"].get("v_str"):
            print("  -> SUCCESS!")
            return True
        else:
            print(f"  -> ERROR: {data.get('message')}")
    except Exception as e:
        print(f"  -> EXCEPTION: {e}")
    return False

endpoints = [
    "api16-normal-v6.tiktokv.com",
    "api16-normal-c-useast1a.tiktokv.com",
    "api16-normal-c-useast2a.tiktokv.com",
    "api16-normal-useast5.us.tiktokv.com",
    "api22-normal-c-useast1a.tiktokv.com",
    "api22-normal-c-useast2a.tiktokv.com"
]

for ep in endpoints:
    test_tiktok(ep)
