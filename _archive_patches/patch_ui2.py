import sys

with open('ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """    def _flow_name_from_current_tab(self) -> str:
        cur = self._active_leaf_tab()
        if cur is self.tab_text:
            return "text_to_video"
        if cur is self.tab_grok_text:
            return "grok_text_to_video"
        if cur is self.tab_image:
            return "image_to_video"
        if cur is self.tab_grok_image:
            return "grok_image_to_video"
        if cur is self.tab_idea:
            return "idea_to_video"
        if cur is self.tab_copy_video:
            return "copy_video"
        if cur is self.tab_create_image:
            return "create_image"
        if cur is self.tab_grok_create_image:
            return "grok_create_image_prompt"
        if cur is self.tab_grok_settings:
            return "grok_settings"
        if cur is self.tab_char_sync:
            return "character_sync\"""

replacement = """    def _flow_name_from_current_tab(self) -> str:
        cur = self._active_leaf_tab()
        if cur is self.tab_text:
            return "text_to_video"
        if cur is self.tab_grok_text:
            return "grok_text_to_video"
        if cur is self.tab_image:
            return "image_to_video"
        if cur is self.tab_grok_image:
            return "grok_image_to_video"
        if cur is self.tab_idea:
            return "idea_to_video"
        if cur is self.tab_copy_video:
            return "copy_video"
        if cur is self.tab_create_image:
            return "create_image"
        if cur is self.tab_grok_create_image:
            return "grok_create_image_prompt"
        if cur is self.tab_grok_settings:
            return "grok_settings"
        if cur is self.tab_char_sync:
            return "character_sync"
        if cur is self.tab_grok_char_sync:
            return "grok_character_sync\"""

if target in content:
    content = content.replace(target, replacement)
    with open('ui.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced successfully (flow_name)")
else:
    print("Target string not found in ui.py (flow_name)")
