# Patch storytelling_exporter.py for normalize_tts_provider
with open('storytelling_exporter.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_norm = """    if provider == "voicebox":
        return "voicebox"
    return "auto" """

new_norm = """    if provider == "voicebox":
        return "voicebox"
    if provider == "tiktok":
        return "tiktok"
    return "auto" """

if "provider == \"tiktok\":" not in content:
    content = content.replace("    if provider == \"voicebox\":\n        return \"voicebox\"\n    return \"auto\"", new_norm)

with open('storytelling_exporter.py', 'w', encoding='utf-8') as f:
    f.write(content)

import shutil
try:
    shutil.copy('storytelling_exporter.py', r'dist\VEO_4.0_V2.2.6_PROMAX\_internal\storytelling_exporter.py')
except Exception:
    pass

print("Patched _normalize_tts_provider for tiktok")
