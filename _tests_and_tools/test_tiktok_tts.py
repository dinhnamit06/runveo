import requests
import base64

def test_tiktok():
    url = "https://api16-normal-useast5.us.tiktokv.com/media/api/text/speech/invoke/"
    headers = {
        "User-Agent": "com.zhiliaoapp.musically/2022600030 (Linux; U; Android 7.1.2; en_US; SM-G988N; Build/NRD90M;tt-ok/3.12.13.1)",
        "Cookie": "sessionid=test"
    }
    payload = {
        "req_text": "Chào các bạn, đây là giọng đọc thử nghiệm.",
        "text_speaker": "vn_female_001",
        "speaker_map_type": 0,
        "aid": 1180
    }
    print(f"Requesting: {url}")
    try:
        response = requests.post(url, headers=headers, params=payload, timeout=10)
        data = response.json()
        print(f"Status Code: {data.get('status_code')}")
        print(f"Message: {data.get('message')}")
        if data.get("data") and data["data"].get("v_str"):
            print("SUCCESS! Voice data received.")
            with open("test_tiktok.mp3", "wb") as f:
                f.write(base64.b64decode(data["data"]["v_str"]))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_tiktok()
