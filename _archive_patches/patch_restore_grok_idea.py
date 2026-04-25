with open('ui.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Add initialization and addTab for tab_grok_idea
target1 = """        self.tab_grok_create_image = CreateImageFromPromptTab()
        self.tab_grok_char_sync = CharacterSyncTab()
        self.tab_grok_settings = GrokSettingsTab(config=self._cfg)
        self.grok_tabs.addTab(self.tab_grok_text, icon(""), "Text to Video")
        self.grok_tabs.addTab(self.tab_grok_image, icon(""), "Image to Video")
        self.grok_tabs.addTab(self.tab_grok_char_sync, icon(""), "Đồng nhất nhân vật")
        self.grok_tabs.addTab(self.tab_grok_settings, icon(""), "Cài đặt")"""

replacement1 = """        self.tab_grok_create_image = CreateImageFromPromptTab()
        self.tab_grok_char_sync = CharacterSyncTab()
        self.tab_grok_settings = GrokSettingsTab(config=self._cfg)
        self.tab_grok_idea = IdeaToVideoTab(config=self._cfg)
        self.grok_tabs.addTab(self.tab_grok_text, icon(""), "Text to Video")
        self.grok_tabs.addTab(self.tab_grok_image, icon(""), "Image to Video")
        self.grok_tabs.addTab(self.tab_grok_idea, icon(""), "Ý tưởng to Video")
        self.grok_tabs.addTab(self.tab_grok_char_sync, icon(""), "Đồng nhất nhân vật")
        self.grok_tabs.addTab(self.tab_grok_settings, icon(""), "Cài đặt")"""

# 2. Add to _update_start_button_for_tab
target2 = """        elif cur is self.tab_idea:
            self.btn_start.setText(f"{platform_prefix} - Tạo từ Ý tưởng")
            self.btn_start.setObjectName("Accent")"""

replacement2 = """        elif cur is self.tab_idea or cur is getattr(self, "tab_grok_idea", None):
            self.btn_start.setText(f"{platform_prefix} - Tạo từ Ý tưởng")
            self.btn_start.setObjectName("Accent")"""

# 3. Add to _flow_name_from_current_tab
target3 = """        if cur is self.tab_idea:
            return "idea_to_video"
        if cur is self.tab_copy_video:"""

replacement3 = """        if cur is self.tab_idea:
            return "idea_to_video"
        if cur is getattr(self, "tab_grok_idea", None):
            return "grok_idea_to_video"
        if cur is self.tab_copy_video:"""

# 4. Handle flow_name in _on_start_stop
target4 = """        if flow_name == "idea_to_video":
            if self.status.isRunning() or self._queue_worker.is_busy():
                QMessageBox.information(self, "Đang chạy", "Queue đang chạy. Tab Ý tưởng hiện chưa đưa vào queue tự động.")
                return
            idea_settings = self.tab_idea.get_settings()"""

replacement4 = """        if flow_name in ("idea_to_video", "grok_idea_to_video"):
            if self.status.isRunning() or self._queue_worker.is_busy():
                QMessageBox.information(self, "Đang chạy", "Queue đang chạy. Tab Ý tưởng hiện chưa đưa vào queue tự động.")
                return
            idea_tab = self.tab_grok_idea if flow_name == "grok_idea_to_video" else self.tab_idea
            idea_settings = idea_tab.get_settings()"""

if target1 in code:
    code = code.replace(target1, replacement1)
if target2 in code:
    code = code.replace(target2, replacement2)
if target3 in code:
    code = code.replace(target3, replacement3)
if target4 in code:
    code = code.replace(target4, replacement4)

with open('ui.py', 'w', encoding='utf-8') as f:
    f.write(code)

try:
    with open(r'dist\VEO_4.0_V2.2.6_PROMAX\_internal\ui.py', 'w', encoding='utf-8') as f:
        f.write(code)
except Exception:
    pass

print("Restored tab_grok_idea in ui.py")
