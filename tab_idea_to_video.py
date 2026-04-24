from __future__ import annotations

import re
import tempfile

from PyQt6.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QIntValidator
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from tts_voices import EDGE_TTS_DEFAULT, get_edge_tts_choices
from voice_profiles import get_voice_choices


STYLE_OPTIONS: list[str] = [
    "3d_Pixar",
    "Realistic",
    "Hyper_Realistic",
    "Live_action_cinematic",
    "2d_Cartoon",
    "3d_Cartoon",
    "3D_CGI_Realistic",
    "Stick_Figure",
    "Comic_Western",
    "Manga_Black_White",
    "Flat_Illustration_2D",
    "Low_Poly_3D",
    "Anime_Japan",
    "CCTV_Found_Footage",
    "Documentary_style",
    "Epic_survival_cinematic",
    "Experimental_Art_film",
    "Music_Video_Aestheticic",
    "Noir_Black_and_White",
    "Pixel_Art_8bit",
    "POV_First_person",
    "Realistic_CGI",
    "Reallistic_CGI",
    "Theatrical_Stage_performance",
    "Vintage_Rentro",
]


INPUT_MODE_OPTIONS: list[tuple[str, str]] = [
    ("Tự nhập", "manual"),
    ("Từ link", "link"),
    ("Từ file PDF", "pdf"),
]


SOURCE_KIND_OPTIONS: list[tuple[str, str]] = [
    ("Tự động", "auto"),
    ("Báo", "news"),
    ("Truyện chữ", "story"),
    ("Truyện tranh", "comic"),
]


OUTPUT_MODE_OPTIONS: list[tuple[str, str]] = [
    ("Video", "video"),
    ("Ảnh storytelling", "storytelling_image"),
]


TTS_PROVIDER_OPTIONS: list[tuple[str, str]] = [
    ("Tự động (Edge TTS -> Windows)", "auto"),
    ("Edge TTS", "edge"),
    ("Windows SAPI", "sapi"),
    ("Voicebox (Local API)", "voicebox"),
    ("Tắt voice", "off"),
]


LANGUAGE_OPTIONS: list[str] = [
    "Tiếng Việt (vi-VN)",
    "English (en-US)",
    "中文 (zh-CN)",
]


class _TTSPreviewWorker(QThread):
    completed = pyqtSignal(bool, str, str)

    def __init__(self, text: str, provider: str, voice_key: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._text = str(text or "").strip()
        self._provider = str(provider or "edge").strip()
        self._voice_key = str(voice_key or "").strip()

    def run(self) -> None:
        try:
            from storytelling_exporter import create_tts_preview

            out_path = create_tts_preview(
                self._text,
                tempfile.gettempdir(),
                voice_key=self._voice_key,
                tts_provider=self._provider,
            )
            self.completed.emit(True, out_path, "")
        except BaseException as exc:
            self.completed.emit(False, "", str(exc))



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


class IdeaToVideoTab(QWidget):
    def __init__(self, config=None, parent: QWidget | None = None):
        super().__init__(parent)
        self._cfg = config
        self.setObjectName("IdeaToVideoTab")
        self.setStyleSheet(
            """
            QWidget#IdeaToVideoTab {
                background: #edf4ff;
            }
            QWidget#IdeaToVideoTab QLabel {
                font-size: 14px;
            }
            QWidget#IdeaToVideoTab QGroupBox {
                font-size: 14px;
                font-weight: 800;
                border: 1px solid #c8d7f2;
                border-radius: 8px;
                margin-top: 8px;
                background: #eaf2ff;
            }
            QWidget#IdeaToVideoTab QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QWidget#IdeaToVideoTab QLineEdit,
            QWidget#IdeaToVideoTab QComboBox {
                font-size: 13px;
                min-height: 32px;
                background: #f3f8ff;
            }
            QWidget#IdeaToVideoTab QComboBox QAbstractItemView {
                background: #f3f8ff;
                selection-background-color: #dbeafe;
                outline: none;
            }
            QWidget#IdeaToVideoTab QComboBox QAbstractItemView::item {
                min-height: 32px;
                padding: 4px 8px;
            }
            QWidget#IdeaToVideoTab QPlainTextEdit {
                font-size: 14px;
                background: #f1f7ff;
                border: 1px solid #c8d7f2;
                border-radius: 8px;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        cfg_box = QGroupBox("Cấu hình")
        cfg_box.setStyleSheet("QGroupBox{font-weight:800;}")
        cfg_layout = QFormLayout(cfg_box)
        cfg_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        cfg_layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        cfg_layout.setHorizontalSpacing(10)
        cfg_layout.setVerticalSpacing(6)

        self.source_mode = QComboBox()
        for label, value in INPUT_MODE_OPTIONS:
            self.source_mode.addItem(label, value)
        source_mode_default = str(getattr(self._cfg, "idea_source_mode", "manual") if self._cfg is not None else "manual")
        source_mode_idx = self.source_mode.findData(source_mode_default)
        self.source_mode.setCurrentIndex(source_mode_idx if source_mode_idx >= 0 else 0)
        cfg_layout.addRow("Nguồn nội dung:", self.source_mode)

        self.source_kind = QComboBox()
        for label, value in SOURCE_KIND_OPTIONS:
            self.source_kind.addItem(label, value)
        source_kind_default = str(getattr(self._cfg, "idea_source_kind", "auto") if self._cfg is not None else "auto")
        source_kind_idx = self.source_kind.findData(source_kind_default)
        self.source_kind.setCurrentIndex(source_kind_idx if source_kind_idx >= 0 else 0)
        cfg_layout.addRow("Loại nguồn:", self.source_kind)

        self.source_url = QLineEdit()
        self.source_url.setPlaceholderText("Dán link báo/truyện chữ/truyện tranh hoặc link PDF tại đây")
        self.source_url.setText(str(getattr(self._cfg, "idea_source_url", "") if self._cfg is not None else ""))
        cfg_layout.addRow("Link nguồn:", self.source_url)

        self.pdf_wrap = QWidget()
        pdf_layout = QHBoxLayout(self.pdf_wrap)
        pdf_layout.setContentsMargins(0, 0, 0, 0)
        pdf_layout.setSpacing(8)
        self.source_pdf_path = QLineEdit()
        self.source_pdf_path.setReadOnly(True)
        self.source_pdf_path.setPlaceholderText("Chọn file PDF truyện tranh/truyện chữ nếu chọn Từ file PDF")
        self.source_pdf_path.setText(str(getattr(self._cfg, "idea_source_pdf_path", "") if self._cfg is not None else ""))
        self.btn_select_pdf = QPushButton("Duyệt")
        self.btn_select_pdf.setFixedWidth(92)
        self.btn_select_pdf.clicked.connect(self._browse_pdf)
        pdf_layout.addWidget(self.source_pdf_path, 1)
        pdf_layout.addWidget(self.btn_select_pdf)
        cfg_layout.addRow("File PDF:", self.pdf_wrap)
        
        self.cfg_layout = cfg_layout

        self.output_mode = QComboBox()
        for label, value in OUTPUT_MODE_OPTIONS:
            self.output_mode.addItem(label, value)
        output_mode_default = str(getattr(self._cfg, "idea_output_mode", "video") if self._cfg is not None else "video")
        output_mode_idx = self.output_mode.findData(output_mode_default)
        self.output_mode.setCurrentIndex(output_mode_idx if output_mode_idx >= 0 else 0)
        cfg_layout.addRow("Kiểu xuất:", self.output_mode)

        scene_default = str(getattr(self._cfg, "idea_scene_count", 1) if self._cfg is not None else 1)
        self.scene_count = QLineEdit(scene_default)
        self.scene_count.setValidator(QIntValidator(1, 100, self.scene_count))
        self.scene_count.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.scene_count.setFixedWidth(110)
        cfg_layout.addRow("Số cảnh (mỗi cảnh 8s):", self.scene_count)

        self.style_combo = QComboBox()
        self.style_combo.addItems(STYLE_OPTIONS)
        style_default = str(getattr(self._cfg, "idea_style", "3d_Pixar") if self._cfg is not None else "3d_Pixar")
        self.style_combo.setCurrentText(style_default if style_default in STYLE_OPTIONS else "3d_Pixar")
        self.style_combo.setMinimumWidth(280)
        cfg_layout.addRow("Phong cách:", self.style_combo)

        self.dialogue_lang = QComboBox()
        self.dialogue_lang.addItems(LANGUAGE_OPTIONS)
        lang_default = str(
            getattr(self._cfg, "idea_dialogue_language", "Tiếng Việt (vi-VN)")
            if self._cfg is not None
            else "Tiếng Việt (vi-VN)"
        )
        self.dialogue_lang.setCurrentText(lang_default if lang_default in LANGUAGE_OPTIONS else "Tiếng Việt (vi-VN)")
        self.dialogue_lang.setMinimumWidth(240)
        cfg_layout.addRow("Ngôn ngữ thoại:", self.dialogue_lang)

        self.tts_provider = QComboBox()
        for label, value in TTS_PROVIDER_OPTIONS:
            self.tts_provider.addItem(label, value)
        tts_default = str(getattr(self._cfg, "idea_tts_provider", "auto") if self._cfg is not None else "auto")
        tts_idx = self.tts_provider.findData(tts_default)
        self.tts_provider.setCurrentIndex(tts_idx if tts_idx >= 0 else 0)
        self.tts_provider.setMinimumWidth(240)
        cfg_layout.addRow("TTS:", self.tts_provider)

        self.voice_wrap = QWidget()
        voice_layout = QHBoxLayout(self.voice_wrap)
        voice_layout.setContentsMargins(0, 0, 0, 0)
        voice_layout.setSpacing(8)
        self.voice_profile = QComboBox()
        self.voice_profile.setMinimumWidth(240)
        self.btn_preview_voice = QPushButton("▶ Nghe thử")
        self.btn_preview_voice.setFixedWidth(104)
        self.btn_preview_voice.clicked.connect(self._preview_tts_voice)
        voice_layout.addWidget(self.voice_profile, 1)
        voice_layout.addWidget(self.btn_preview_voice)
        cfg_layout.addRow("Giọng đọc:", self.voice_wrap)
        
        self.audio_player = AudioPlayerWidget()
        cfg_layout.addRow("", self.audio_player)
        
        self.voicebox_id_wrap = QWidget()
        vb_layout = QHBoxLayout(self.voicebox_id_wrap)
        vb_layout.setContentsMargins(0, 0, 0, 0)
        self.voicebox_id = QComboBox()
        self.voicebox_id.setEditable(True)
        self.voicebox_id.setMinimumWidth(180)
        
        self.btn_refresh_vb = QPushButton("Lấy danh sách giọng")
        self.btn_refresh_vb.setFixedWidth(130)
        self.btn_refresh_vb.clicked.connect(self._fetch_voicebox_voices)
        
        saved_id = str(getattr(self._cfg, "idea_voicebox_id", "") if self._cfg is not None else "")
        if saved_id:
            self.voicebox_id.addItem(saved_id, saved_id)
            self.voicebox_id.setCurrentText(saved_id)
            
        vb_layout.addWidget(self.voicebox_id, 1)
        vb_layout.addWidget(self.btn_refresh_vb)
        cfg_layout.addRow("Voice ID (Voicebox):", self.voicebox_id_wrap)

        self._voice_combo_mode = ""
        self._preview_worker: _TTSPreviewWorker | None = None
        self._refresh_voice_choices()

        try:
            self.source_mode.currentIndexChanged.connect(self._on_source_mode_changed)
            self.source_kind.currentIndexChanged.connect(lambda _=0: self._persist_config())
            self.source_url.editingFinished.connect(self._persist_config)
            self.source_pdf_path.editingFinished.connect(self._persist_config)
            self.output_mode.currentIndexChanged.connect(self._on_output_mode_changed)
            self.scene_count.editingFinished.connect(self._persist_config)
            self.style_combo.currentTextChanged.connect(lambda _=None: self._persist_config())
            self.dialogue_lang.currentTextChanged.connect(self._on_dialogue_language_changed)
            self.voice_profile.currentIndexChanged.connect(lambda _=0: self._persist_config())
            self.tts_provider.currentIndexChanged.connect(self._on_tts_provider_changed)
            self.voicebox_id.currentTextChanged.connect(lambda _=None: self._persist_config())
        except Exception:
            pass

        root.addWidget(cfg_box)

        self.script_title = QLabel("Kịch bản/ Ý tưởng:")
        self.script_title.setStyleSheet("font-weight: 700; color: #1f2d48; font-size: 14px;")
        root.addWidget(self.script_title)

        self.idea_editor = QPlainTextEdit()
        self.idea_editor.setPlaceholderText(
            "Nhập kịch bản/ý tưởng tại đây\n"
            "Tool tự động xây dựng nhân vật, bối cảnh rồi viết prompt\n"
            "Tool tự động tạo video và tải về.\n"
            "(Có Thể dùng ChatGPT để viết kịch bản chi tiết và dán vào đây.)"
        )
        self.idea_editor.setMinimumHeight(120)
        root.addWidget(self.idea_editor, 1)

        self.stretch_widget = QWidget()
        root.addWidget(self.stretch_widget, 0)

        self._update_visibility()



    def _on_source_mode_changed(self) -> None:
        self._persist_config()
        self._update_visibility()

    def _on_output_mode_changed(self) -> None:
        self._refresh_voice_choices()
        self._persist_config()
        self._update_visibility()

    def _on_tts_provider_changed(self) -> None:
        self._refresh_voice_choices()
        self._persist_config()
        self._update_visibility()

    def _on_dialogue_language_changed(self) -> None:
        self._refresh_voice_choices()
        self._persist_config()
        self._update_visibility()

    def _selected_dialogue_locale(self) -> str:
        text = self.dialogue_lang.currentText().strip()
        match = re.search(r"\(([a-z]{2,3}(?:-[A-Z]{2})?)\)", text)
        return match.group(1) if match else "vi-VN"

    def _refresh_voice_choices(self) -> None:
        if not hasattr(self, "voice_profile"):
            return
        output_mode = str(self.output_mode.currentData() or "video")
        provider = str(self.tts_provider.currentData() or "auto") if hasattr(self, "tts_provider") else "auto"
        locale = self._selected_dialogue_locale()
        current = str(self.voice_profile.currentData() or "").strip()
        self.voice_profile.blockSignals(True)
        self.voice_profile.clear()

        if output_mode == "storytelling_image" and provider in {"auto", "edge"}:
            self._voice_combo_mode = "edge"
            choices = get_edge_tts_choices(locale)
            default_key = str(getattr(self._cfg, "idea_tts_voice", "") if self._cfg is not None else "") or EDGE_TTS_DEFAULT
            for key, label in choices:
                self.voice_profile.addItem(label, key)
            idx = self.voice_profile.findData(current) if current else -1
            if idx < 0:
                idx = self.voice_profile.findData(default_key)
            if idx < 0:
                idx = self.voice_profile.findData(EDGE_TTS_DEFAULT)
            self.voice_profile.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            self._voice_combo_mode = "profile"
            default_key = str(getattr(self._cfg, "idea_voice_profile", "None_NoVoice") if self._cfg is not None else "None_NoVoice")
            for key, label in get_voice_choices(locale, include_none=True):
                self.voice_profile.addItem(label, key)
            idx = self.voice_profile.findData(current) if current else -1
            if idx < 0:
                idx = self.voice_profile.findData(default_key)
            self.voice_profile.setCurrentIndex(idx if idx >= 0 else 0)

        self.voice_profile.blockSignals(False)


    def _fetch_voicebox_voices(self) -> None:
        import urllib.request
        import json
        from PyQt6.QtWidgets import QMessageBox, QApplication
        self.btn_refresh_vb.setText("Đang lấy...")
        self.btn_refresh_vb.setEnabled(False)
        QApplication.processEvents()
        
        found_voices = []
        ports = [17493, 8000]
        endpoints = ['/v1/voices', '/api/voices', '/voices', '/v1/models']
        
        for port in ports:
            for ep in endpoints:
                try:
                    url = f"http://127.0.0.1:{port}{ep}"
                    req = urllib.request.Request(url, headers={'Accept': 'application/json'})
                    with urllib.request.urlopen(req, timeout=2) as response:
                        data = json.loads(response.read().decode('utf-8'))
                        items = []
                        if isinstance(data, list):
                            items = data
                        elif isinstance(data, dict) and 'data' in data:
                            items = data['data']
                        elif isinstance(data, dict) and 'voices' in data:
                            items = data['voices']
                            
                        for item in items:
                            if isinstance(item, dict):
                                v_id = item.get('id') or item.get('voice_id') or item.get('name')
                                v_name = item.get('name') or item.get('id') or v_id
                                if v_id:
                                    found_voices.append((str(v_name), str(v_id)))
                        if found_voices:
                            break
                except Exception:
                    pass
            if found_voices:
                break
                
        self.btn_refresh_vb.setText("Lấy danh sách giọng")
        self.btn_refresh_vb.setEnabled(True)
        
        if found_voices:
            self.voicebox_id.clear()
            for name, vid in found_voices:
                self.voicebox_id.addItem(name, vid)
            QMessageBox.information(self, "Thành công", f"Đã lấy được {len(found_voices)} giọng từ Voicebox!")
        else:
            QMessageBox.warning(self, "Lỗi kết nối", "Không lấy được danh sách giọng. Hãy chắc chắn Voicebox đang chạy.\nBạn vẫn có thể gõ tên/ID giọng thủ công vào ô thả xuống.")

    def _preview_tts_voice(self) -> None:
        output_mode = str(self.output_mode.currentData() or "video")
        provider = str(self.tts_provider.currentData() or "auto")
        if output_mode != "storytelling_image" or provider == "off":
            QMessageBox.information(self, "Nghe thử", "Chỉ nghe thử TTS khi chọn Kiểu xuất Ảnh storytelling.")
            return

        voice_key = str(self.voicebox_id.currentText() or "").strip() if provider == "voicebox" else str(self.voice_profile.currentData() or "").strip()
        if not voice_key and provider != "off":
            QMessageBox.warning(self, "Thiếu giọng", "Chưa nhập Voice ID hoặc chưa chọn giọng đọc để nghe thử.")
            return

        preview_provider = "edge" if provider == "auto" and self._voice_combo_mode == "edge" else provider
        sample_text = "Xin chào, đây là giọng đọc thử cho video kể chuyện."
        if self._selected_dialogue_locale().startswith("en"):
            sample_text = "Hello, this is a voice preview for storytelling video."
        elif self._selected_dialogue_locale().startswith("zh"):
            sample_text = "你好，这是讲故事视频的语音试听。"

        self.btn_preview_voice.setEnabled(False)
        self.btn_preview_voice.setText("Đang tạo...")
        self._preview_worker = _TTSPreviewWorker(sample_text, preview_provider, voice_key, self)
        self._preview_worker.completed.connect(self._on_tts_preview_complete)
        self._preview_worker.start()

    def _on_tts_preview_complete(self, ok: bool, path: str, message: str) -> None:
        self.btn_preview_voice.setEnabled(True)
        self.btn_preview_voice.setText("▶ Nghe thử")
        self._preview_worker = None
        if not ok:
            QMessageBox.warning(self, "Không nghe thử được", message or "Không tạo được file nghe thử.")
            return
        self.audio_player.set_source(path)

    def _update_visibility(self) -> None:
        mode = str(self.source_mode.currentData() or "manual")
        output_mode = str(self.output_mode.currentData() or "video")
        tts_provider = str(self.tts_provider.currentData() or "auto") if hasattr(self, "tts_provider") else "auto"
        
        is_link = mode == "link"
        self.source_url.setVisible(is_link)
        link_label = self.cfg_layout.labelForField(self.source_url)
        if link_label:
            link_label.setVisible(is_link)
            
        is_pdf = mode == "pdf"
        self.pdf_wrap.setVisible(is_pdf)
        pdf_label = self.cfg_layout.labelForField(self.pdf_wrap)
        if pdf_label:
            pdf_label.setVisible(is_pdf)
            
        is_manual = mode == "manual"
        self.script_title.setVisible(is_manual)
        self.idea_editor.setVisible(is_manual)

        is_storytelling = output_mode == "storytelling_image"
        voice_visible = output_mode == "video" or (is_storytelling and tts_provider != "off")
        self.voice_wrap.setVisible(voice_visible)
        voice_label = self.cfg_layout.labelForField(self.voice_wrap)
        if voice_label:
            voice_label.setVisible(voice_visible)
        is_voicebox = (tts_provider == "voicebox")
        self.voicebox_id_wrap.setVisible(is_storytelling and is_voicebox)
        vb_label = self.cfg_layout.labelForField(self.voicebox_id_wrap)
        if vb_label:
            vb_label.setVisible(is_storytelling and is_voicebox)
            
        self.voice_wrap.setVisible(is_storytelling and tts_provider != "off" and not is_voicebox)
        voice_label = self.cfg_layout.labelForField(self.voice_wrap)
        if voice_label:
            voice_label.setVisible(is_storytelling and tts_provider != "off" and not is_voicebox)
            
        self.btn_preview_voice.setVisible(is_storytelling and tts_provider != "off")

        self.tts_provider.setVisible(is_storytelling)
        tts_label = self.cfg_layout.labelForField(self.tts_provider)
        if tts_label:
            tts_label.setVisible(is_storytelling)
        
        if is_manual:
            self.layout().setStretchFactor(self.idea_editor, 1)
            self.layout().setStretchFactor(self.stretch_widget, 0)
        else:
            self.layout().setStretchFactor(self.idea_editor, 0)
            self.layout().setStretchFactor(self.stretch_widget, 1)

    def _browse_pdf(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn file PDF nguồn",
            self.source_pdf_path.text().strip(),
            "Tệp PDF (*.pdf);;Tất cả tệp (*.*)",
        )
        if not file_path:
            return
        self.source_pdf_path.setText(file_path)
        self.source_mode.setCurrentIndex(max(0, self.source_mode.findData("pdf")))
        if self.source_kind.currentData() == "auto":
            comic_idx = self.source_kind.findData("comic")
            if comic_idx >= 0:
                self.source_kind.setCurrentIndex(comic_idx)
        self._persist_config()

    def get_scene_count(self) -> int:
        try:
            val = int((self.scene_count.text() or "1").strip())
        except Exception:
            return 1
        return max(1, min(100, val))

    def get_settings(self) -> dict[str, str | int]:
        output_mode = str(self.output_mode.currentData() or "video")
        provider = str(self.tts_provider.currentData() or "auto")
        current_voice = str(self.voice_profile.currentData() or "None_NoVoice")
        tts_voice = current_voice if output_mode == "storytelling_image" and provider != "off" else ""
        prompt_voice = current_voice if self._voice_combo_mode == "profile" else str(getattr(self._cfg, "idea_voice_profile", "None_NoVoice") if self._cfg is not None else "None_NoVoice")
        return {
            "voicebox_id": self.voicebox_id.currentText().strip(),
            "source_mode": str(self.source_mode.currentData() or "manual"),
            "source_kind": str(self.source_kind.currentData() or "auto"),
            "source_url": self.source_url.text().strip(),
            "source_pdf_path": self.source_pdf_path.text().strip(),
            "output_mode": output_mode,
            "scene_count": self.get_scene_count(),
            "style": self.style_combo.currentText().strip(),
            "dialogue_language": self.dialogue_lang.currentText().strip(),
            "voice_profile": prompt_voice or "None_NoVoice",
            "tts_provider": provider,
            "tts_voice": tts_voice,
            "idea": self.idea_editor.toPlainText().strip(),
        }

    def _persist_config(self) -> None:
        if self._cfg is None:
            return
        try:
            setattr(self._cfg, "idea_scene_count", self.get_scene_count())
            setattr(self._cfg, "idea_style", self.style_combo.currentText().strip() or "3d_Pixar")
            setattr(self._cfg, "idea_source_mode", str(self.source_mode.currentData() or "manual"))
            setattr(self._cfg, "idea_source_kind", str(self.source_kind.currentData() or "auto"))
            setattr(self._cfg, "idea_source_url", self.source_url.text().strip())
            setattr(self._cfg, "idea_source_pdf_path", self.source_pdf_path.text().strip())
            setattr(self._cfg, "idea_output_mode", str(self.output_mode.currentData() or "video"))
            setattr(
                self._cfg,
                "idea_dialogue_language",
                self.dialogue_lang.currentText().strip() or "Tiếng Việt (vi-VN)",
            )
            current_voice = str(self.voice_profile.currentData() or "").strip()
            if self._voice_combo_mode == "profile":
                setattr(self._cfg, "idea_voice_profile", current_voice or "None_NoVoice")
                if str(self.output_mode.currentData() or "") == "storytelling_image":
                    setattr(self._cfg, "idea_tts_voice", current_voice or "None_NoVoice")
            elif self._voice_combo_mode == "edge":
                setattr(self._cfg, "idea_tts_voice", current_voice or EDGE_TTS_DEFAULT)
            setattr(self._cfg, "idea_tts_provider", str(self.tts_provider.currentData() or "auto"))
            self._cfg.save()
        except Exception:
            pass
