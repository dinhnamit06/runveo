import sys
import json

with open('status_panel.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """            # Use Grok for image generation
            payload = {"description": prompt_text, "source_type": "grok"}
            self.table.setItem(row, self.col_payload, QTableWidgetItem(json.dumps(payload, ensure_ascii=False)))"""

patch = """            # Use Grok for image generation
            payload = {"description": prompt_text, "source_type": "grok"}
            aspect_ratio = str(raw.get("aspect_ratio") or "").strip()
            if aspect_ratio:
                payload["aspect_ratio"] = aspect_ratio
            mode = str(raw.get("mode") or "").strip()
            if mode:
                payload["mode"] = mode
            self.table.setItem(row, self.col_payload, QTableWidgetItem(json.dumps(payload, ensure_ascii=False)))"""

if target in content:
    content = content.replace(target, patch)

with open('status_panel.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched status_panel.py for Grok Create Image settings extraction")
