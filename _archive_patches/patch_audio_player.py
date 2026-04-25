import sys

with open('tab_idea_to_video.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Patch 1: AudioPlayerWidget Class
class_patch = """
from PyQt6.QtWidgets import QSlider
class AudioPlayerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(1.0)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.btn_play = QPushButton("▶")
        self.btn_play.setFixedWidth(30)
        self.btn_play.clicked.connect(self.toggle_playback)
        
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.sliderMoved.connect(self.set_position)
        
        layout.addWidget(self.btn_play)
        layout.addWidget(self.slider)
        
        self.player.positionChanged.connect(self.position_changed)
        self.player.durationChanged.connect(self.duration_changed)
        self.player.playbackStateChanged.connect(self.state_changed)
        self.setVisible(False)
        
    def set_source(self, path):
        self.player.setSource(QUrl.fromLocalFile(path))
        self.setVisible(True)
        self.player.play()
        
    def toggle_playback(self):
        from PyQt6.QtMultimedia import QMediaPlayer
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()
            
    def state_changed(self, state):
        from PyQt6.QtMultimedia import QMediaPlayer
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.btn_play.setText("⏸")
        else:
            self.btn_play.setText("▶")
            
    def position_changed(self, position):
        self.slider.setValue(position)
        
    def duration_changed(self, duration):
        self.slider.setRange(0, duration)
        
    def set_position(self, position):
        self.player.setPosition(position)


class IdeaToVideoTab(QWidget):"""

content = content.replace("class IdeaToVideoTab(QWidget):", class_patch)

# Patch 2: Add audio player to layout
init_target = """        self.btn_preview_voice = QPushButton("▶ Nghe thử")
        self.btn_preview_voice.setFixedWidth(104)
        self.btn_preview_voice.clicked.connect(self._preview_tts_voice)
        voice_layout.addWidget(self.voice_profile, 1)
        voice_layout.addWidget(self.btn_preview_voice)
        cfg_layout.addRow("Giọng đọc:", self.voice_wrap)
        self._voice_combo_mode = ""
        self._preview_worker: _TTSPreviewWorker | None = None
        self._refresh_voice_choices()"""

init_patch = """        self.btn_preview_voice = QPushButton("▶ Nghe thử")
        self.btn_preview_voice.setFixedWidth(104)
        self.btn_preview_voice.clicked.connect(self._preview_tts_voice)
        voice_layout.addWidget(self.voice_profile, 1)
        voice_layout.addWidget(self.btn_preview_voice)
        cfg_layout.addRow("Giọng đọc:", self.voice_wrap)
        
        self.audio_player = AudioPlayerWidget()
        cfg_layout.addRow("", self.audio_player)
        
        self._voice_combo_mode = ""
        self._preview_worker: _TTSPreviewWorker | None = None
        self._refresh_voice_choices()"""

content = content.replace(init_target, init_patch)

# Patch 3: Use the embedded audio player
play_target = """    def _on_tts_preview_complete(self, ok: bool, path: str, message: str) -> None:
        self.btn_preview_voice.setEnabled(True)
        self.btn_preview_voice.setText("▶ Nghe thử")
        self._preview_worker = None
        if not ok:
            QMessageBox.warning(self, "Không nghe thử được", message or "Không tạo được file nghe thử.")
            return
        self._media_player.setSource(QUrl.fromLocalFile(path))
        self._media_player.play()"""

play_patch = """    def _on_tts_preview_complete(self, ok: bool, path: str, message: str) -> None:
        self.btn_preview_voice.setEnabled(True)
        self.btn_preview_voice.setText("▶ Nghe thử")
        self._preview_worker = None
        if not ok:
            QMessageBox.warning(self, "Không nghe thử được", message or "Không tạo được file nghe thử.")
            return
        self.audio_player.set_source(path)"""

content = content.replace(play_target, play_patch)

# Remove the old QMediaPlayer from __init__
old_media_player = """        self._media_player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._media_player.setAudioOutput(self._audio_output)
        self._audio_output.setVolume(1.0)"""
content = content.replace(old_media_player, "")

with open('tab_idea_to_video.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched tab_idea_to_video.py")
