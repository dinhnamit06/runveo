import sys

with open('ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Patch 1: Add tab_grok_idea
init_target = """        self.tab_grok_char_sync = CharacterSyncTab()
        self.tab_grok_settings = GrokSettingsTab(config=self._cfg)
        self.grok_tabs.addTab(self.tab_grok_text, icon(""), "Text to Video")
        self.grok_tabs.addTab(self.tab_grok_image, icon(""), "Image to Video")
        self.grok_tabs.addTab(self.tab_grok_char_sync, icon(""), "Đồng nhất nhân vật")
        self.grok_tabs.addTab(self.tab_grok_settings, icon(""), "Cài đặt")"""

init_patch = """        self.tab_grok_idea = IdeaToVideoTab(config)
        self.tab_grok_char_sync = CharacterSyncTab()
        self.tab_grok_settings = GrokSettingsTab(config=self._cfg)
        self.grok_tabs.addTab(self.tab_grok_text, icon(""), "Text to Video")
        self.grok_tabs.addTab(self.tab_grok_image, icon(""), "Image to Video")
        self.grok_tabs.addTab(self.tab_grok_idea, icon(""), "Ý tưởng to Video")
        self.grok_tabs.addTab(self.tab_grok_char_sync, icon(""), "Đồng nhất nhân vật")
        self.grok_tabs.addTab(self.tab_grok_settings, icon(""), "Cài đặt")"""

if init_target in content:
    content = content.replace(init_target, init_patch)

# Patch 2: _update_start_button_text
btn_target = """        elif cur is self.tab_idea:
            self.btn_start.setText(f"{platform_prefix} - Ý Tưởng -> Kịch Bản -> Video")
            self.btn_start.setObjectName("Accent")"""

btn_patch = """        elif cur is self.tab_idea or cur is self.tab_grok_idea:
            self.btn_start.setText(f"{platform_prefix} - Ý Tưởng -> Kịch Bản -> Video")
            self.btn_start.setObjectName("Accent")"""

if btn_target in content:
    content = content.replace(btn_target, btn_patch)

# Patch 3: _flow_name_from_current_tab
flow_target = """        if cur is self.tab_idea:
            return "idea_to_video"
        if cur is self.tab_copy_video:"""

flow_patch = """        if cur is self.tab_idea:
            return "idea_to_video"
        if cur is getattr(self, "tab_grok_idea", None):
            return "grok_idea_to_video"
        if cur is self.tab_copy_video:"""

if flow_target in content:
    content = content.replace(flow_target, flow_patch)

# Patch 4: _on_start_stop
start_target = """        if flow_name == "idea_to_video":
            if self.status.isRunning() or self._queue_worker.is_busy():
                QMessageBox.information(self, "Đang chạy", "Queue đang chạy. Tab Ý tưởng hiện chưa đưa vào queue tự động.")
                return"""

start_patch = """        if flow_name == "grok_idea_to_video":
            if self.status.isRunning() or self._queue_worker.is_busy():
                QMessageBox.information(self, "Đang chạy", "Queue đang chạy.")
                return
            idea_settings = self.tab_grok_idea.get_settings()
            idea_settings["video_model"] = "GROK"
            try:
                self.status.start_idea_to_video(idea_settings)
            except Exception as exc:
                QMessageBox.critical(self, "Lỗi Idea to Video", f"Không thể khởi động Idea to Video: {exc}")
            return

        if flow_name == "idea_to_video":
            if self.status.isRunning() or self._queue_worker.is_busy():
                QMessageBox.information(self, "Đang chạy", "Queue đang chạy. Tab Ý tưởng hiện chưa đưa vào queue tự động.")
                return"""

if start_target in content:
    content = content.replace(start_target, start_patch)

with open('ui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched ui.py for grok idea to video")
