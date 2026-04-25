import requests
from settings_manager import SettingsManager

def probe_voices():
    cfg = SettingsManager.load_config()
    session_id = cfg.get("TIKTOK_SESSION_ID") or cfg.get("tiktok_session_id")
    url = "https://api16-normal-v6.tiktokv.com/media/api/text/speech/invoke/"
    headers = {
        "User-Agent": "com.zhiliaoapp.musically/2022600030 (Linux; U; Android 7.1.2; en_US; SM-G988N; Build/NRD90M;tt-ok/3.12.13.1)",
        "Cookie": f"sessionid={session_id.strip()}"
    }
    
    prefixes = ["vi", "vn", "vnm", "viet", "vietnamese"]
    suffixes = ["001", "002", "003", "004", "female", "male", "001_female", "002_male", "003_female", "004_male"]
    
    candidates = []
    for p in prefixes:
        for s in suffixes:
            candidates.append(f"{p}_{s}")
            
    print(f"Probing {len(candidates)} candidates...")
    
    for v in candidates:
        payload = {
            "req_text": "Xin chào",
            "text_speaker": v,
            "speaker_map_type": 0,
            "aid": 1180
        }
        try:
            response = requests.post(url, headers=headers, params=payload, timeout=3)
            data = response.json()
            if data.get("status_code") == 0 and data.get("data") and data["data"].get("v_str"):
                print(f"FOUND: {v}")
        except Exception:
            pass

probe_voices()
