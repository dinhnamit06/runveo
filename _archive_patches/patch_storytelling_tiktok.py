# Patch storytelling_exporter.py
with open('storytelling_exporter.py', 'r', encoding='utf-8') as f:
    content = f.read()

import_tiktok = """
from tts_voices import EDGE_TTS_DEFAULT, get_edge_tts_voice_metadata, is_edge_tts_voice_key
from tiktok_tts_exporter import tiktok_tts_save
from settings_manager import SettingsManager
"""

content = content.replace("from tts_voices import EDGE_TTS_DEFAULT, get_edge_tts_voice_metadata, is_edge_tts_voice_key", import_tiktok)

tiktok_logic = """
    if clean_text:
        is_tiktok = str(voice_key or "").strip().startswith("tiktok_")
        
        if is_tiktok:
            try:
                cfg = SettingsManager.load_settings()
                if not isinstance(cfg, dict): cfg = {}
                session_id = str(cfg.get("tiktok_session_id") or "").strip()
                ok = tiktok_tts_save(clean_text, edge_path, voice_key, session_id)
            except Exception as exc:
                if callable(log): log(f"Lỗi Tiktok TTS: {exc}")
                ok = False
            
            if ok:
                duration = _probe_duration(edge_path) or duration_hint
                return edge_path, duration
            else:
                if callable(log):
                    log("⚠️ Tiktok TTS lỗi hoặc thiếu Session ID; chuyển sang audio im lặng.")
                _silent_audio(silent_path, duration_hint)
                return silent_path, duration_hint

        try:
"""

content = content.replace('    if clean_text:\n        try:', tiktok_logic)

with open('storytelling_exporter.py', 'w', encoding='utf-8') as f:
    f.write(content)

try:
    import shutil
    shutil.copy('storytelling_exporter.py', r'dist\VEO_4.0_V2.2.6_PROMAX\_internal\storytelling_exporter.py')
    shutil.copy('tiktok_tts_exporter.py', r'dist\VEO_4.0_V2.2.6_PROMAX\_internal\tiktok_tts_exporter.py')
except Exception:
    pass

print("Patched storytelling_exporter for TikTok TTS!")
