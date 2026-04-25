import sys
import os

with open('ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace import
if 'from qt_ui.tab_grok_create_image import GrokCreateImageTab' not in content:
    content = content.replace('from tab_create_image import CreateImageTab, CreateImageFromPromptTab', 'from tab_create_image import CreateImageTab, CreateImageFromPromptTab\nfrom qt_ui.tab_grok_create_image import GrokCreateImageTab')

# Replace instantiation
content = content.replace('self.tab_grok_create_image = CreateImageFromPromptTab()', 'self.tab_grok_create_image = GrokCreateImageTab()')

# Pass settings to enqueue
target = """            items = [{"id": str(i + 1), "description": str(p)} for i, p in enumerate(prompts) if str(p).strip()]
            payload = self.status.enqueue_grok_create_image(items)"""

patch = """            items = [{"id": str(i + 1), "description": str(p)} for i, p in enumerate(prompts) if str(p).strip()]
            settings = self.tab_grok_create_image.get_settings()
            for item in items:
                item.update(settings)
            payload = self.status.enqueue_grok_create_image(items)"""

if target in content:
    content = content.replace(target, patch)

with open('ui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched ui.py to use GrokCreateImageTab")
