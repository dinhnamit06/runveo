# -*- coding: utf-8 -*-
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from voice_profiles import get_best_voice, get_voice_choices


TARGET_LANGUAGE_OPTIONS: list[tuple[str, str]] = [
    ("Tiếng Anh (Mỹ)", "en-US"),
    ("Tiếng Việt", "vi-VN"),
    ("Tiếng Tây Ban Nha (Tây Ban Nha)", "es-ES"),
    ("Tiếng Tây Ban Nha (Mexico)", "es-MX"),
    ("Tiếng Trung", "zh-CN"),
    ("Tiếng Nhật", "ja-JP"),
    ("Tiếng Hàn", "ko-KR"),
]


STYLE_OPTIONS: list[str] = [
    "Tự động nhận diện",
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


class CopyVideoTab(QWidget):
    def __init__(self, config=None, parent: QWidget | None = None):
        super().__init__(parent)
        self._cfg = config
        self._voice_keys: list[str] = []
        self.setObjectName("CopyVideoTab")
        self.setStyleSheet(
            """
            QWidget#CopyVideoTab {
                background: #edf4ff;
            }
            QWidget#CopyVideoTab QGroupBox {
                font-size: 14px;
                font-weight: 800;
                border: 1px solid #c8d7f2;
                border-radius: 8px;
                margin-top: 8px;
                background: #eaf2ff;
            }
            QWidget#CopyVideoTab QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QWidget#CopyVideoTab QLineEdit,
            QWidget#CopyVideoTab QComboBox {
                font-size: 13px;
                min-height: 32px;
                background: #f3f8ff;
            }
            QWidget#CopyVideoTab QPlainTextEdit {
                font-size: 13px;
                min-height: 82px;
                background: #f3f8ff;
                border: 1px solid #c8d7f2;
                border-radius: 8px;
                padding: 6px 8px;
            }
            QWidget#CopyVideoTab QLabel {
                color: #1f2d48;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        cfg_box = QGroupBox("Sao chép video")
        cfg_layout = QFormLayout(cfg_box)
        cfg_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        cfg_layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        cfg_layout.setHorizontalSpacing(10)
        cfg_layout.setVerticalSpacing(8)

        file_wrap = QWidget()
        file_layout = QHBoxLayout(file_wrap)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(8)
        self.video_path = QLineEdit()
        self.video_path.setReadOnly(True)
        self.video_path.setPlaceholderText("Chọn video nguồn (.mp4, .mov, .mkv)...")
        self.video_path.setText(str(getattr(self._cfg, "copy_video_path", "") or ""))
        self.btn_select_video = QPushButton("Duyệt")
        self.btn_select_video.setFixedWidth(92)
        self.btn_select_video.clicked.connect(self._browse_video)
        file_layout.addWidget(self.video_path, 1)
        file_layout.addWidget(self.btn_select_video)
        cfg_layout.addRow("Video nguồn:", file_wrap)

        self.cb_target_lang = QComboBox()
        for label, locale in TARGET_LANGUAGE_OPTIONS:
            self.cb_target_lang.addItem(label, locale)
        target_default = str(getattr(self._cfg, "copy_video_target_language", "en-US") or "en-US")
        lang_idx = self.cb_target_lang.findData(target_default)
        self.cb_target_lang.setCurrentIndex(lang_idx if lang_idx >= 0 else 0)
        cfg_layout.addRow("Ngôn ngữ đích:", self.cb_target_lang)

        self.cb_voice_actor = QComboBox()
        cfg_layout.addRow("Giọng đọc:", self.cb_voice_actor)

        self.cb_video_model = QComboBox()
        self.cb_video_model.addItems(["VEO 3", "GROK"])
        model_default = str(getattr(self._cfg, "copy_video_model", "VEO 3") or "VEO 3")
        self.cb_video_model.setCurrentText(model_default if model_default in {"VEO 3", "GROK"} else "VEO 3")
        cfg_layout.addRow("Model Video:", self.cb_video_model)

        self.cb_style = QComboBox()
        self.cb_style.addItems(STYLE_OPTIONS)
        style_default = str(getattr(self._cfg, "copy_video_style", "Tự động nhận diện") or "Tự động nhận diện")
        self.cb_style.setCurrentText(style_default if style_default in STYLE_OPTIONS else "Tự động nhận diện")
        cfg_layout.addRow("Phong cách video:", self.cb_style)

        strength_wrap = QWidget()
        strength_layout = QHBoxLayout(strength_wrap)
        strength_layout.setContentsMargins(0, 0, 0, 0)
        strength_layout.setSpacing(8)
        self.copy_strength_slider = QSlider(Qt.Orientation.Horizontal)
        self.copy_strength_slider.setRange(50, 100)
        self.copy_strength_slider.setSingleStep(5)
        self.copy_strength_slider.setPageStep(10)
        self.copy_strength_slider.setTickInterval(10)
        self.copy_strength_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.copy_strength_spin = QSpinBox()
        self.copy_strength_spin.setRange(50, 100)
        self.copy_strength_spin.setSingleStep(5)
        self.copy_strength_spin.setSuffix("%")
        self.copy_strength_spin.setFixedWidth(86)
        strength_default = self._normalize_copy_strength(
            getattr(self._cfg, "copy_video_strength", 100) if self._cfg is not None else 100
        )
        self.copy_strength_slider.setValue(strength_default)
        self.copy_strength_spin.setValue(strength_default)
        strength_layout.addWidget(self.copy_strength_slider, 1)
        strength_layout.addWidget(self.copy_strength_spin)
        cfg_layout.addRow("Độ copy:", strength_wrap)

        self.user_idea = QPlainTextEdit()
        self.user_idea.setPlaceholderText(
            "Tùy chọn: nhập yêu cầu chỉnh sửa khi sao chép, ví dụ đổi nhân vật, đổi bối cảnh, đổi nghề nghiệp, đổi cảm xúc..."
        )
        self.user_idea.setPlainText(str(getattr(self._cfg, "copy_video_user_idea", "") or ""))
        cfg_layout.addRow("Ý tưởng chỉnh sửa:", self.user_idea)

        self.chk_auto_run = QCheckBox("Tự render ngay sau khi đổ dữ liệu")
        self.chk_auto_run.setChecked(bool(getattr(self._cfg, "copy_video_auto_run", False)))
        cfg_layout.addRow("", self.chk_auto_run)

        root.addWidget(cfg_box)

        helper_box = QGroupBox("Quy trình")
        helper_layout = QVBoxLayout(helper_box)
        helper_layout.setContentsMargins(12, 10, 12, 10)
        helper_layout.setSpacing(6)
        helper_layout.addWidget(QLabel("1. Chọn video nguồn"))
        helper_layout.addWidget(QLabel("2. Chọn ngôn ngữ đích"))
        helper_layout.addWidget(QLabel("3. Chọn giọng đọc theo ngôn ngữ và fallback"))
        helper_layout.addWidget(QLabel("4. Chọn độ copy 50%-100%"))
        helper_layout.addWidget(QLabel("5. Nhập ý tưởng chỉnh sửa nếu muốn biến đổi nội dung khi sao chép"))
        helper_layout.addWidget(QLabel("6. Bấm Start để phân tích, đổ scene và tự render nếu cần"))
        root.addWidget(helper_box)
        root.addStretch(1)

        self.cb_target_lang.currentIndexChanged.connect(self._on_target_language_changed)
        self.cb_voice_actor.currentIndexChanged.connect(lambda _=0: self._persist_config())
        self.chk_auto_run.toggled.connect(lambda _=False: self._persist_config())
        self.cb_style.currentTextChanged.connect(lambda _=None: self._persist_config())
        self.cb_video_model.currentTextChanged.connect(lambda _=None: self._persist_config())
        self.copy_strength_slider.valueChanged.connect(self.copy_strength_spin.setValue)
        self.copy_strength_spin.valueChanged.connect(self.copy_strength_slider.setValue)
        self.copy_strength_spin.valueChanged.connect(lambda _=0: self._persist_config())
        self.user_idea.textChanged.connect(self._persist_config)

        self._refresh_voice_choices(
            preferred_key=str(getattr(self._cfg, "copy_video_voice_profile", "None_NoVoice") or "None_NoVoice")
        )

    def _browse_video(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn video nguồn",
            self.video_path.text().strip(),
            "Tệp video (*.mp4 *.mov *.avi *.mkv *.webm *.m4v);;Tất cả tệp (*.*)",
        )
        if not file_path:
            return
        self.video_path.setText(file_path)
        self._persist_config()

    def _on_target_language_changed(self) -> None:
        self._refresh_voice_choices(preferred_key=self.selected_voice_key())
        self._persist_config()

    def _refresh_voice_choices(self, preferred_key: str | None = None) -> None:
        target_locale = self.selected_target_language()
        preferred = str(preferred_key or "").strip()
        if not preferred:
            preferred = str(getattr(self._cfg, "copy_video_voice_profile", "") or "").strip()
        if not preferred:
            preferred = get_best_voice(target_locale)

        current_key = preferred if preferred else get_best_voice(target_locale)
        choices = get_voice_choices(target_language=target_locale, include_none=True)
        self._voice_keys = [key for key, _ in choices]

        self.cb_voice_actor.blockSignals(True)
        self.cb_voice_actor.clear()
        for key, label in choices:
            self.cb_voice_actor.addItem(label, key)

        idx = self.cb_voice_actor.findData(current_key)
        if idx < 0:
            idx = self.cb_voice_actor.findData(get_best_voice(target_locale, preferred_key=current_key))
        self.cb_voice_actor.setCurrentIndex(idx if idx >= 0 else 0)
        self.cb_voice_actor.blockSignals(False)

    def selected_target_language(self) -> str:
        return str(self.cb_target_lang.currentData() or "en-US")

    def selected_voice_key(self) -> str:
        return str(self.cb_voice_actor.currentData() or "None_NoVoice")

    @staticmethod
    def _normalize_copy_strength(value) -> int:
        try:
            strength = int(value)
        except Exception:
            strength = 100
        return max(50, min(100, strength))

    def copy_strength(self) -> int:
        return self._normalize_copy_strength(self.copy_strength_spin.value())

    def get_settings(self) -> dict[str, str | bool | int]:
        return {
            "video_path": self.video_path.text().strip(),
            "target_language": self.selected_target_language(),
            "voice_actor_key": self.selected_voice_key(),
            "auto_run": bool(self.chk_auto_run.isChecked()),
            "style": self.cb_style.currentText().strip(),
            "copy_strength": self.copy_strength(),
            "user_idea": self.user_idea.toPlainText().strip(),
            "video_model": self.cb_video_model.currentText().strip(),
        }

    def _persist_config(self) -> None:
        if self._cfg is None:
            return
        try:
            setattr(self._cfg, "copy_video_path", self.video_path.text().strip())
            setattr(self._cfg, "copy_video_target_language", self.selected_target_language())
            setattr(self._cfg, "copy_video_voice_profile", self.selected_voice_key())
            setattr(self._cfg, "copy_video_auto_run", bool(self.chk_auto_run.isChecked()))
            setattr(self._cfg, "copy_video_style", self.cb_style.currentText().strip())
            setattr(self._cfg, "copy_video_strength", self.copy_strength())
            setattr(self._cfg, "copy_video_user_idea", self.user_idea.toPlainText().strip())
            setattr(self._cfg, "copy_video_model", self.cb_video_model.currentText().strip())
            self._cfg.save()
        except Exception:
            pass
