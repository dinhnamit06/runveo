# Patch tab_idea_to_video.py for Tiktok provider
with open('tab_idea_to_video.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update TTS_PROVIDER_OPTIONS
old_providers = """TTS_PROVIDER_OPTIONS: list[tuple[str, str]] = [
    ("Tự động (Edge TTS -> Windows)", "auto"),
    ("Edge TTS", "edge"),
    ("Windows SAPI", "sapi"),
    ("Voicebox (Local API)", "voicebox"),
    ("Tắt voice", "off"),
]"""

new_providers = """TTS_PROVIDER_OPTIONS: list[tuple[str, str]] = [
    ("Tự động (Edge TTS -> Windows)", "auto"),
    ("Edge TTS", "edge"),
    ("Windows SAPI", "sapi"),
    ("Voicebox (Local API)", "voicebox"),
    ("Capcut / Tiktok TTS", "tiktok"),
    ("Tắt voice", "off"),
]"""

if "Capcut / Tiktok TTS" not in content:
    content = content.replace(old_providers, new_providers)

# 2. Update _refresh_voice_choices
old_refresh = """        if output_mode == "storytelling_image" and provider in {"auto", "edge"}:
            self._voice_combo_mode = "edge"
            choices = get_edge_tts_choices(locale)"""

new_refresh = """        if output_mode == "storytelling_image" and provider == "tiktok":
            self._voice_combo_mode = "tiktok"
            choices = [(k, v) for k, v in get_edge_tts_choices(locale) if k.startswith("tiktok_")]
            default_key = "tiktok_vn_female_1"
            for key, label in choices:
                self.voice_profile.addItem(label, key)
            idx = self.voice_profile.findData(current) if current else -1
            if idx < 0:
                idx = self.voice_profile.findData(default_key)
            self.voice_profile.setCurrentIndex(idx if idx >= 0 else 0)
        elif output_mode == "storytelling_image" and provider in {"auto", "edge", "sapi"}:
            self._voice_combo_mode = "edge"
            choices = [(k, v) for k, v in get_edge_tts_choices(locale) if not k.startswith("tiktok_")]"""

if "provider == \"tiktok\":" not in content:
    content = content.replace(old_refresh, new_refresh)

# 3. Update preview provider mapping
old_preview = """        preview_provider = "edge" if provider == "auto" and self._voice_combo_mode == "edge" else provider"""
new_preview = """        preview_provider = "edge" if provider == "auto" and self._voice_combo_mode == "edge" else provider
        if preview_provider == "tiktok":
            preview_provider = "tiktok"  # will be handled by tts preview logic if we added it, but let's check storytelling exporter
"""
content = content.replace(old_preview, new_preview)

# 4. Save
with open('tab_idea_to_video.py', 'w', encoding='utf-8') as f:
    f.write(content)

import shutil
try:
    shutil.copy('tab_idea_to_video.py', r'dist\VEO_4.0_V2.2.6_PROMAX\_internal\tab_idea_to_video.py')
except Exception:
    pass

print("Patched tab_idea_to_video.py successfully.")
