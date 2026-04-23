from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIntValidator
from PyQt6.QtWidgets import (QComboBox, QFormLayout, QGroupBox, QLabel, QLineEdit, 
                             QPlainTextEdit, QVBoxLayout, QWidget, QCheckBox, QPushButton, QHBoxLayout, QFileDialog)
from voice_profiles import VOICE_JSON, VOICE_OPTIONS

STYLE_OPTIONS: list[str] = [
    '3d_Pixar', 'Realistic', 'Live_action_cinematic', '2d_Cartoon', '3d_Cartoon',
    '3D_CGI_Realistic', 'Anime_Japan', 'CCTV_Found_Footage', 'Documentary_style',
    'Epic_survival_cinematic', 'Experimental_Art_film', 'Music_Video_Aestheticic',
    'Noir_Black_and_White', 'Pixel_Art_8bit', 'POV_First_person', 'Realistic_CGI',
    'Reallistic_CGI', 'Theatrical_Stage_performance', 'Vintage_Rentro'
]

LANGUAGE_OPTIONS: list[str] = [
    'Tiếng Việt (vi-VN)', 'English (en-US)', '中文 (zh-CN)'
]

class IdeaToVideoTab(QWidget):
    def __init__(self, config, parent: QWidget | None = None):
        super().__init__(parent)
        self._cfg = config
        self.setObjectName('IdeaToVideoTab')
        self.setStyleSheet("""
            QWidget#IdeaToVideoTab {
                background: #0f172a;
            }
            QWidget#IdeaToVideoTab QLabel {
                font-size: 14px;
            }
            QWidget#IdeaToVideoTab QGroupBox {
                font-size: 14px;
                font-weight: 800;
                border: 1px solid #334155;
                border-radius: 8px;
                margin-top: 8px;
                background: #1e293b;
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
                background: #1e293b;
            }
            QWidget#IdeaToVideoTab QComboBox QAbstractItemView {
                background: #1e293b;
                selection-background-color: #4f46e5;
                outline: none;
            }
            QWidget#IdeaToVideoTab QComboBox QAbstractItemView::item {
                min-height: 32px;
                padding: 4px 8px;
            }
            QWidget#IdeaToVideoTab QPlainTextEdit {
                font-size: 14px;
                background: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
            }
            """)
        
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)
        
        cfg_box = QGroupBox('Cấu hình')
        cfg_box.setStyleSheet('QGroupBox{font-weight:800;}')
        cfg_layout = QFormLayout(cfg_box)
        cfg_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        cfg_layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        cfg_layout.setHorizontalSpacing(10)
        cfg_layout.setVerticalSpacing(6)
        
        scene_default = str(getattr(self._cfg, 'idea_scene_count', 1)) if self._cfg else '1'
        self.scene_count = QLineEdit(scene_default)
        self.scene_count.setValidator(QIntValidator(1, 100, self.scene_count))
        self.scene_count.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.scene_count.setFixedWidth(110)
        cfg_layout.addRow('Số cảnh (mỗi cảnh 8s):', self.scene_count)
        
        self.style_combo = QComboBox()
        self.style_combo.addItems(STYLE_OPTIONS)
        style_default = str(getattr(self._cfg, 'idea_style', '3d_Pixar')) if self._cfg else '3d_Pixar'
        self.style_combo.setCurrentText(style_default if style_default in STYLE_OPTIONS else '3d_Pixar')
        self.style_combo.setMinimumWidth(280)
        cfg_layout.addRow('Phong cách:', self.style_combo)
        
        self.dialogue_lang = QComboBox()
        self.dialogue_lang.addItems(LANGUAGE_OPTIONS)
        lang_default = str(getattr(self._cfg, 'idea_dialogue_language', 'Tiếng Việt (vi-VN)')) if self._cfg else 'Tiếng Việt (vi-VN)'
        self.dialogue_lang.setCurrentText(lang_default if lang_default in LANGUAGE_OPTIONS else 'Tiếng Việt (vi-VN)')
        self.dialogue_lang.setMinimumWidth(240)
        cfg_layout.addRow('Ngôn ngữ thoại:', self.dialogue_lang)

        # Voice Actor selection
        voice_items = [VOICE_JSON[k]["label"] for k in VOICE_OPTIONS]
        self.voice_profile = QComboBox()
        self.voice_profile.addItems(voice_items)
        v_default = str(getattr(self._cfg, 'idea_voice_profile', 'None_NoVoice') or 'None_NoVoice')
        if v_default in VOICE_OPTIONS:
            self.voice_profile.setCurrentIndex(VOICE_OPTIONS.index(v_default))
        cfg_layout.addRow('Giọng đọc:', self.voice_profile)

        # Clone Mode UI
        self.chk_clone_mode = QCheckBox('Chế độ Clone (Bóc băng từ Video)')
        self.chk_clone_mode.setStyleSheet('font-weight:700; color:#10b981;')
        cfg_layout.addRow('', self.chk_clone_mode)

        self.video_path_container = QWidget()
        vp_layout = QHBoxLayout(self.video_path_container)
        vp_layout.setContentsMargins(0, 0, 0, 0)
        self.video_path_edit = QLineEdit()
        self.video_path_edit.setPlaceholderText('Đường dẫn file video (.mp4, .mov)...')
        self.btn_browse_video = QPushButton('Chọn Video')
        self.btn_browse_video.setFixedWidth(100)
        vp_layout.addWidget(self.video_path_edit)
        vp_layout.addWidget(self.btn_browse_video)
        self.video_path_container.setVisible(False)
        cfg_layout.addRow('Video gốc:', self.video_path_container)

        self.chk_auto_run = QCheckBox('Tự động chạy (Render ngay khi bóc xong)')
        cfg_layout.addRow('', self.chk_auto_run)

        # Connections
        self.scene_count.editingFinished.connect(self._persist_config)
        self.style_combo.currentTextChanged.connect(lambda _: self._persist_config())
        self.dialogue_lang.currentTextChanged.connect(lambda _: self._persist_config())
        self.voice_profile.currentIndexChanged.connect(lambda _: self._persist_config())
        self.chk_clone_mode.toggled.connect(self._on_clone_mode_toggled)
        self.btn_browse_video.clicked.connect(self._browse_video)
        
        root.addWidget(cfg_box)
        
        script_title = QLabel('Kịch bản/ Ý tưởng:')
        script_title.setStyleSheet('font-weight: 700; color: #f8fafc; font-size: 14px;')
        root.addWidget(script_title)
        
        self.idea_editor = QPlainTextEdit()
        self.idea_editor.setPlaceholderText('Nhập kịch bản/ý tưởng tại đây\nTool tự động xây dựng nhân vật, bối cảnh rồi viết prompt\nTool tự động tạo video và tải về.\n(Có Thể dùng ChatGPT để viết kịch bản chi tiết và dán vào đây.)')
        self.idea_editor.setMinimumHeight(260)
        root.addWidget(self.idea_editor, 1)

    def get_scene_count(self) -> int:
        try:
            val = int(self.scene_count.text().strip())
            return max(1, min(100, val))
        except Exception:
            return 1

    def get_settings(self) -> dict[str, str | int | bool]:
        return {
            'scene_count': self.get_scene_count(),
            'style': self.style_combo.currentText().strip(),
            'dialogue_language': self.dialogue_lang.currentText().strip(),
            'idea': self.idea_editor.toPlainText().strip(),
            'voice_profile': self.voice_profile.currentData() or VOICE_OPTIONS[self.voice_profile.currentIndex()],
            'clone_mode': self.chk_clone_mode.isChecked(),
            'video_path': self.video_path_edit.text().strip(),
            'auto_run': self.chk_auto_run.isChecked()
        }

    def _persist_config(self) -> None:
        if self._cfg is None:
            return
        try:
            setattr(self._cfg, 'idea_scene_count', self.get_scene_count())
            
            style = self.style_combo.currentText().strip()
            if style:
                setattr(self._cfg, 'idea_style', '3d_Pixar') # Disassembly suggests it forces '3d_Pixar' if style exists? Wait.
                # Disassembly:
                # 218 COPY 1
                # 220 TO_BOOL
                # 228 POP_JUMP_IF_TRUE 2 (to 234)
                # 232 POP_TOP
                # 234 LOAD_CONST '3d_Pixar'
                # 236 CALL 3
                # It seems it sets '3d_Pixar' if style is truthy? No, `setattr(self._cfg, 'idea_style', style or '3d_Pixar')` logic.
                # Let's re-read disassembly carefully.
                # 142 LOAD_ATTR style_combo
                # 162 LOAD_ATTR currentText
                # 182 CALL 0
                # 190 LOAD_ATTR strip
                # 210 CALL 0
                # 218 COPY 1
                # 220 TO_BOOL
                # 228 POP_JUMP_IF_TRUE 2 (to 234)
                # 232 POP_TOP
                # 234 LOAD_CONST '3d_Pixar'
                # This pattern `x or 'default'` compiles to `COPY 1, TO_BOOL, POP_JUMP_IF_TRUE, POP_TOP, LOAD_CONST`.
                # So it is `style or '3d_Pixar'`.
            setattr(self._cfg, 'idea_style', style or '3d_Pixar')
            
            lang = self.dialogue_lang.currentText().strip()
            setattr(self._cfg, 'idea_dialogue_language', lang or 'Tiếng Việt (vi-VN)')
            
            v_idx = self.voice_profile.currentIndex()
            if 0 <= v_idx < len(VOICE_OPTIONS):
                setattr(self._cfg, 'idea_voice_profile', VOICE_OPTIONS[v_idx])

            self._cfg.save()
        except Exception:
            pass

    def _on_clone_mode_toggled(self, checked: bool) -> None:
        self.video_path_container.setVisible(checked)
        self.idea_editor.setVisible(not checked)
        # Change placeholder or label if needed
        self._persist_config()

    def _browse_video(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn Video Gốc", "", "Video Files (*.mp4 *.mov *.avi *.mkv)"
        )
        if file_path:
            self.video_path_edit.setText(file_path)
            self._persist_config()
