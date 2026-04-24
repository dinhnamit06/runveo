import sys

with open('ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """        self.tab_grok_create_image = CreateImageFromPromptTab()
        self.tab_grok_settings = GrokSettingsTab(config=self._cfg)
        self.grok_tabs.addTab(self.tab_grok_text, icon(""), "Text to Video")
        self.grok_tabs.addTab(self.tab_grok_image, icon(""), "Image to Video")
        self.grok_tabs.addTab(self.tab_grok_settings, icon(""), "Cài đặt")"""

replacement = """        self.tab_grok_create_image = CreateImageFromPromptTab()
        self.tab_grok_char_sync = CharacterSyncTab()
        self.tab_grok_settings = GrokSettingsTab(config=self._cfg)
        self.grok_tabs.addTab(self.tab_grok_text, icon(""), "Text to Video")
        self.grok_tabs.addTab(self.tab_grok_image, icon(""), "Image to Video")
        self.grok_tabs.addTab(self.tab_grok_char_sync, icon(""), "Đồng nhất nhân vật")
        self.grok_tabs.addTab(self.tab_grok_settings, icon(""), "Cài đặt")"""

if target in content:
    content = content.replace(target, replacement)
    with open('ui.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced successfully")
else:
    print("Target string not found in ui.py")
