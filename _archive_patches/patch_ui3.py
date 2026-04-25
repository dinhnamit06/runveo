import sys

with open('ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """        if not video_path:
            QMessageBox.warning(self, "Thiếu video", "Hãy chọn video nguồn ở tab SAO CHÉP VIDEO.")
            return
        self.status.start_copy_video(
            video_path,
            target_language,
            voice_actor_key,
            auto_run,
            style,
            copy_strength,
            user_idea,
        )"""

replacement = """        video_model = str(copy_settings.get("video_model") or "VEO 3").strip()
        if not video_path:
            QMessageBox.warning(self, "Thiếu video", "Hãy chọn video nguồn ở tab SAO CHÉP VIDEO.")
            return
        self.status.start_copy_video(
            video_path,
            target_language,
            voice_actor_key,
            auto_run,
            style,
            copy_strength,
            user_idea,
            video_model,
        )"""

if target in content:
    content = content.replace(target, replacement)
    with open('ui.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced")
else:
    print("Not found")
