import sys

with open('ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

import_line = "from qt_ui.tab_grok_create_image import GrokCreateImageTab\n"

if "from qt_ui.tab_grok_create_image import GrokCreateImageTab" not in content:
    # Insert it after "from tab_settings import SettingsTab"
    content = content.replace(
        "from tab_settings import SettingsTab\n",
        "from tab_settings import SettingsTab\n" + import_line
    )
    with open('ui.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched ui.py to import GrokCreateImageTab")
else:
    print("GrokCreateImageTab already imported in ui.py")
