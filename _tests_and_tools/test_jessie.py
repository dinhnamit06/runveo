import sys
from settings_manager import SettingsManager
from tiktok_tts_exporter import tiktok_tts_save
import os

cfg = SettingsManager.load_config()
session_id = cfg.get("TIKTOK_SESSION_ID")

success = tiktok_tts_save("Hello, this is a voice preview", "test_preview_jessie.mp3", "tiktok_en_us_jessie", session_id)
print("Jessie Success:", success)
if success:
    print("File size:", os.path.getsize("test_preview_jessie.mp3"))
