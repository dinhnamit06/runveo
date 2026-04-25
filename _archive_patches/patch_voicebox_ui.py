import sys

with open('tab_idea_to_video.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Patch 1: Add voicebox_id text input
init_target = """        self.audio_player = AudioPlayerWidget()
        cfg_layout.addRow("", self.audio_player)
        
        self._voice_combo_mode = ""
        self._preview_worker: _TTSPreviewWorker | None = None
        self._refresh_voice_choices()"""

init_patch = """        self.audio_player = AudioPlayerWidget()
        cfg_layout.addRow("", self.audio_player)
        
        self.voicebox_id_wrap = QWidget()
        vb_layout = QHBoxLayout(self.voicebox_id_wrap)
        vb_layout.setContentsMargins(0, 0, 0, 0)
        self.voicebox_id = QLineEdit()
        self.voicebox_id.setPlaceholderText("Nhập Voice ID từ giao diện Voicebox (chỉ dùng cho Voicebox)")
        self.voicebox_id.setText(str(getattr(self._cfg, "idea_voicebox_id", "") if self._cfg is not None else ""))
        vb_layout.addWidget(self.voicebox_id)
        cfg_layout.addRow("Voice ID (Voicebox):", self.voicebox_id_wrap)

        self._voice_combo_mode = ""
        self._preview_worker: _TTSPreviewWorker | None = None
        self._refresh_voice_choices()"""

if init_target in content:
    content = content.replace(init_target, init_patch)

# Patch 2: Add event connection for voicebox_id
try_target = """            self.voice_profile.currentIndexChanged.connect(lambda _=0: self._persist_config())
            self.tts_provider.currentIndexChanged.connect(self._on_tts_provider_changed)
        except Exception:"""

try_patch = """            self.voice_profile.currentIndexChanged.connect(lambda _=0: self._persist_config())
            self.tts_provider.currentIndexChanged.connect(self._on_tts_provider_changed)
            self.voicebox_id.editingFinished.connect(self._persist_config)
        except Exception:"""

if try_target in content:
    content = content.replace(try_target, try_patch)

# Patch 3: Update visibility
vis_target = """        self.btn_preview_voice.setVisible(is_storytelling and tts_provider != "off")

        self.tts_provider.setVisible(is_storytelling)"""

vis_patch = """        is_voicebox = (tts_provider == "voicebox")
        self.voicebox_id_wrap.setVisible(is_storytelling and is_voicebox)
        vb_label = self.cfg_layout.labelForField(self.voicebox_id_wrap)
        if vb_label:
            vb_label.setVisible(is_storytelling and is_voicebox)
            
        self.voice_wrap.setVisible(is_storytelling and tts_provider != "off" and not is_voicebox)
        voice_label = self.cfg_layout.labelForField(self.voice_wrap)
        if voice_label:
            voice_label.setVisible(is_storytelling and tts_provider != "off" and not is_voicebox)
            
        self.btn_preview_voice.setVisible(is_storytelling and tts_provider != "off")

        self.tts_provider.setVisible(is_storytelling)"""

if vis_target in content:
    content = content.replace(vis_target, vis_patch)

# Patch 4: update get_settings
set_target = """        prompt_voice = current_voice if self._voice_combo_mode == "profile" else str(getattr(self._cfg, "idea_voice_profile", "None_NoVoice") if self._cfg is not None else "None_NoVoice")
        return {"""

set_patch = """        prompt_voice = current_voice if self._voice_combo_mode == "profile" else str(getattr(self._cfg, "idea_voice_profile", "None_NoVoice") if self._cfg is not None else "None_NoVoice")
        return {
            "voicebox_id": self.voicebox_id.text().strip(),"""

if set_target in content:
    content = content.replace(set_target, set_patch)

# Patch 5: update _persist_config
per_target = """            setattr(self._cfg, "idea_scene_count", self.get_scene_count())
            setattr(self._cfg, "idea_style", self.style_combo.currentText().strip())
            setattr(self._cfg, "idea_dialogue_language", self.dialogue_lang.currentText().strip())
            setattr(self._cfg, "idea_tts_provider", self.tts_provider.currentData())
            current_voice = self.voice_profile.currentData()"""

per_patch = """            setattr(self._cfg, "idea_scene_count", self.get_scene_count())
            setattr(self._cfg, "idea_style", self.style_combo.currentText().strip())
            setattr(self._cfg, "idea_dialogue_language", self.dialogue_lang.currentText().strip())
            setattr(self._cfg, "idea_tts_provider", self.tts_provider.currentData())
            setattr(self._cfg, "idea_voicebox_id", self.voicebox_id.text().strip())
            current_voice = self.voice_profile.currentData()"""

if per_target in content:
    content = content.replace(per_target, per_patch)

# Patch 6: pass voicebox_id to preview
prev_target = """        voice_key = str(self.voice_profile.currentData() or "").strip()
        if not voice_key:
            QMessageBox.warning(self, "Thiếu giọng", "Chưa chọn giọng đọc để nghe thử.")
            return

        preview_provider = "edge" if provider == "auto" and self._voice_combo_mode == "edge" else provider
        sample_text = "Xin chào, đây là giọng đọc thử cho video kể chuyện."
"""

prev_patch = """        voice_key = str(self.voicebox_id.text() or "").strip() if provider == "voicebox" else str(self.voice_profile.currentData() or "").strip()
        if not voice_key and provider != "off":
            QMessageBox.warning(self, "Thiếu giọng", "Chưa nhập Voice ID hoặc chưa chọn giọng đọc để nghe thử.")
            return

        preview_provider = "edge" if provider == "auto" and self._voice_combo_mode == "edge" else provider
        sample_text = "Xin chào, đây là giọng đọc thử cho video kể chuyện."
"""

if prev_target in content:
    content = content.replace(prev_target, prev_patch)


with open('tab_idea_to_video.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched tab_idea_to_video.py for Voicebox UI")
