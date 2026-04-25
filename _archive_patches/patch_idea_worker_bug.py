import sys

with open('status_panel.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """    def _on_idea_to_video_complete(self, result: dict) -> None:
        self._idea_worker = None"""

patch = """    def _on_idea_to_video_complete(self, result: dict) -> None:
        worker = self._idea_worker
        self._idea_worker = None"""

if target in content:
    content = content.replace(target, patch)

target2 = """        idea_settings = getattr(self._idea_worker, "_idea_settings", {}) if self._idea_worker else {}"""

patch2 = """        idea_settings = getattr(worker, "_idea_settings", {}) if worker else {}"""

if target2 in content:
    content = content.replace(target2, patch2)

with open('status_panel.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed idea worker None bug")
