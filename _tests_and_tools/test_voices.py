import requests
from settings_manager import SettingsManager

def test_voice(voice_id):
    cfg = SettingsManager.load_config()
    session_id = cfg.get("TIKTOK_SESSION_ID") or cfg.get("tiktok_session_id")
    url = "https://api16-normal-v6.tiktokv.com/media/api/text/speech/invoke/"
    headers = {
        "User-Agent": "com.zhiliaoapp.musically/2022600030 (Linux; U; Android 7.1.2; en_US; SM-G988N; Build/NRD90M;tt-ok/3.12.13.1)",
        "Cookie": f"sessionid={session_id.strip()}"
    }
    payload = {
        "req_text": "Hello, this is a test.",
        "text_speaker": voice_id,
        "speaker_map_type": 0,
        "aid": 1180
    }
    print(f"Testing {voice_id}...")
    try:
        response = requests.post(url, headers=headers, params=payload, timeout=5)
        data = response.json()
        if data.get("status_code") == 0 and data.get("data") and data["data"].get("v_str"):
            print("  -> SUCCESS")
        else:
            print(f"  -> ERROR: {data.get('message')}")
    except Exception as e:
        print(f"  -> EXCEPTION: {e}")

voices = [
    "en_us_001", "en_us_002", "vn_001_female", "vn_002_male", "vi_001", "vi_vn_001", "vn_003_female"
]
for v in voices:
    test_voice(v)
