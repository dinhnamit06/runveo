import sys

with open('status_panel.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Patch 1: Pass idea_settings
init_target = """        self._idea_worker = _IdeaToVideoWorker(
            project_name=project_name,
            idea_text=idea_text,
            scene_count=scene_count,
            style=style,
            language=language,
            source_mode=source_mode,
            source_kind=source_kind,
            source_url=source_url,
            source_pdf_path=source_pdf_path,
            output_mode=output_mode,
            parent=self,
        )"""

init_patch = """        self._idea_worker = _IdeaToVideoWorker(
            project_name=project_name,
            idea_text=idea_text,
            scene_count=scene_count,
            style=style,
            language=language,
            source_mode=source_mode,
            source_kind=source_kind,
            source_url=source_url,
            source_pdf_path=source_pdf_path,
            output_mode=output_mode,
            parent=self,
        )
        self._idea_worker._idea_settings = idea_settings"""

if init_target in content:
    content = content.replace(init_target, init_patch)

# Patch 2: _on_idea_to_video_complete GROK routing
comp_target = """        idea_voice_key = str(getattr(self._cfg, "idea_voice_profile", "None_NoVoice") or "None_NoVoice")
        idea_voice_profile_text = get_voice_profile_text(idea_voice_key)
        video_prompt_texts = [
            self._idea_video_prompt_from_prompt_text(prompt_text, idx, idea_voice_profile_text)
            for idx, prompt_text in enumerate(prompt_texts, start=1)
        ]
        self._append_run_log(f"✅ Idea to Video tạo {len(video_prompt_texts)} prompt tiếng Anh chuẩn VEO. Bắt đầu chạy Text to Video...")
        self.start_text_to_video(video_prompt_texts)"""

comp_patch = """        idea_voice_key = str(getattr(self._cfg, "idea_voice_profile", "None_NoVoice") or "None_NoVoice")
        idea_voice_profile_text = get_voice_profile_text(idea_voice_key)
        video_prompt_texts = [
            self._idea_video_prompt_from_prompt_text(prompt_text, idx, idea_voice_profile_text)
            for idx, prompt_text in enumerate(prompt_texts, start=1)
        ]
        
        idea_settings = getattr(self._idea_worker, "_idea_settings", {}) if self._idea_worker else {}
        video_model = str(idea_settings.get("video_model", "VEO 3") or "VEO 3").strip().upper()
        
        self._append_run_log(f"✅ Idea to Video tạo {len(video_prompt_texts)} prompt tiếng Anh chuẩn {video_model}. Bắt đầu chạy Text to Video...")
        
        if video_model == "GROK":
            payload = self.enqueue_grok_text_to_video(video_prompt_texts)
            if payload:
                self.start_queued_job(str(payload.get("mode_key")), list(payload.get("rows")))
        else:
            self.start_text_to_video(video_prompt_texts)"""

if comp_target in content:
    content = content.replace(comp_target, comp_patch)

with open('status_panel.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched status_panel.py for Grok routing")
