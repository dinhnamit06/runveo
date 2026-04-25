# Patch storytelling_exporter.py for SettingsManager.load_config
with open('storytelling_exporter.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_logic = """                cfg = SettingsManager.load_settings()
                if not isinstance(cfg, dict): cfg = {}
                session_id = str(cfg.get("tiktok_session_id") or "").strip()"""

new_logic = """                cfg = SettingsManager.load_config()
                if not isinstance(cfg, dict): cfg = {}
                session_id = str(cfg.get("TIKTOK_SESSION_ID") or cfg.get("tiktok_session_id") or "").strip()"""

if "SettingsManager.load_config()" not in content:
    content = content.replace(old_logic, new_logic)

with open('storytelling_exporter.py', 'w', encoding='utf-8') as f:
    f.write(content)

import shutil
try:
    shutil.copy('storytelling_exporter.py', r'dist\VEO_4.0_V2.2.6_PROMAX\_internal\storytelling_exporter.py')
except Exception:
    pass

print("Patched storytelling_exporter load_config")
