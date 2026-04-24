import sys

with open('status_panel.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Patch 1: start_copy_video signature
target1 = """    def start_copy_video(
        self,
        video_path: str,
        target_language: str,
        voice_actor_key: str,
        auto_run: bool,
        style: str,
        copy_strength: int = 100,
        user_edit_instruction: str = "",
    ) -> None:"""

replacement1 = """    def start_copy_video(
        self,
        video_path: str,
        target_language: str,
        voice_actor_key: str,
        auto_run: bool,
        style: str,
        copy_strength: int = 100,
        user_edit_instruction: str = "",
        video_model: str = "VEO 3",
    ) -> None:"""

# Patch 2: lambda in start_copy_video
target2 = """        self._clone_worker.completed.connect(
            lambda res, voice_key=str(voice_actor_key or "None_NoVoice"), lang=str(target_language or "en-US"), src=str(video_path or ""), ar=bool(auto_run), strength=copy_strength, edit=user_edit_instruction: self._on_copy_video_complete(res, voice_key, lang, ar, src, strength, edit)
        )"""

replacement2 = """        self._clone_worker.completed.connect(
            lambda res, voice_key=str(voice_actor_key or "None_NoVoice"), lang=str(target_language or "en-US"), src=str(video_path or ""), ar=bool(auto_run), strength=copy_strength, edit=user_edit_instruction, vmodel=video_model: self._on_copy_video_complete(res, voice_key, lang, ar, src, strength, edit, vmodel)
        )"""

# Patch 3: _on_copy_video_complete signature
target3 = """    def _on_copy_video_complete(
        self,
        result: dict,
        voice_actor_key: str,
        target_language: str,
        auto_run: bool,
        source_video_path: str,
        copy_strength: int = 100,
        user_edit_instruction: str = "",
    ) -> None:"""

replacement3 = """    def _on_copy_video_complete(
        self,
        result: dict,
        voice_actor_key: str,
        target_language: str,
        auto_run: bool,
        source_video_path: str,
        copy_strength: int = 100,
        user_edit_instruction: str = "",
        video_model: str = "VEO 3",
    ) -> None:"""

# Patch 4: enqueue_copy_video_scenes call in _on_copy_video_complete
target4 = """        payload = self.enqueue_copy_video_scenes(
            copy_data=data,
            voice_actor_key=voice_actor_key,
            target_language=target_language,
            source_video_path=source_video_path,
        )"""

replacement4 = """        payload = self.enqueue_copy_video_scenes(
            copy_data=data,
            voice_actor_key=voice_actor_key,
            target_language=target_language,
            source_video_path=source_video_path,
            video_model=video_model,
        )"""

# Patch 5: enqueue_copy_video_scenes signature
target5 = """    def enqueue_copy_video_scenes(
        self,
        copy_data: dict,
        voice_actor_key: str,
        target_language: str,
        source_video_path: str,
    ) -> dict | None:"""

replacement5 = """    def enqueue_copy_video_scenes(
        self,
        copy_data: dict,
        voice_actor_key: str,
        target_language: str,
        source_video_path: str,
        video_model: str = "VEO 3",
    ) -> dict | None:"""

# Patch 6: change MODE_COPY_VIDEO to MODE_GROK_TEXT_TO_VIDEO
target6 = """        self._sync_stt_and_prompt_ids()
        self._snapshot_output_count_for_rows(rows)
        self._update_empty_state()
        self._mark_rows_pending(rows)
        return {"mode_key": self.MODE_COPY_VIDEO, "rows": rows, "label": "VEO3 - Sao chép video"}"""

replacement6 = """        self._sync_stt_and_prompt_ids()
        self._snapshot_output_count_for_rows(rows)
        self._update_empty_state()
        self._mark_rows_pending(rows)
        
        mode_key = self.MODE_GROK_TEXT_TO_VIDEO if video_model == "GROK" else self.MODE_COPY_VIDEO
        label = "GROK - Sao chép video" if video_model == "GROK" else "VEO3 - Sao chép video"
        
        for r in rows:
            self._set_row_mode_meta(r, mode_key, payload=self._table_data.get(r, {}))
            
        return {"mode_key": mode_key, "rows": rows, "label": label}"""

targets = [target1, target2, target3, target4, target5, target6]
replacements = [replacement1, replacement2, replacement3, replacement4, replacement5, replacement6]

for i, (t, r) in enumerate(zip(targets, replacements)):
    if t in content:
        content = content.replace(t, r)
        print(f"Patched {i+1}")
    else:
        print(f"Target {i+1} not found")

with open('status_panel.py', 'w', encoding='utf-8') as f:
    f.write(content)
