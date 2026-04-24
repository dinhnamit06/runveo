import sys

with open('tab_idea_to_video.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Patch 1: Import QMediaPlayer
import_patch = """from PyQt6.QtGui import QDesktopServices, QIntValidator
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput"""

content = content.replace("from PyQt6.QtGui import QDesktopServices, QIntValidator", import_patch)

# Patch 2: Initialize QMediaPlayer in __init__
init_target = """        self._refresh_voice_choices()
        self._update_visibility()"""

init_patch = """        self._refresh_voice_choices()
        self._update_visibility()

        self._media_player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._media_player.setAudioOutput(self._audio_output)
        self._audio_output.setVolume(1.0)"""

content = content.replace(init_target, init_patch)

# Patch 3: Use QMediaPlayer to play inside the app
play_target = """        if not ok:
            QMessageBox.warning(self, "Không nghe thử được", message or "Không tạo được file nghe thử.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))"""

play_patch = """        if not ok:
            QMessageBox.warning(self, "Không nghe thử được", message or "Không tạo được file nghe thử.")
            return
        self._media_player.setSource(QUrl.fromLocalFile(path))
        self._media_player.play()"""

content = content.replace(play_target, play_patch)

with open('tab_idea_to_video.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched tab_idea_to_video.py")
