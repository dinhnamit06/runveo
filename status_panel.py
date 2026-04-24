# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import re
import importlib.util
import time
import subprocess
import threading
from pathlib import Path
from datetime import datetime

import imageio_ffmpeg

from PyQt6.QtCore import pyqtSignal, Qt, QUrl, QTimer, QSize, QThread
from PyQt6.QtGui import QDesktopServices, QPainter, QColor, QBrush, QPixmap
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QHeaderView,
    QToolButton,
    QMessageBox,
    QStackedWidget,
    QGroupBox,
    QPlainTextEdit,
    QSizePolicy,
    QFileDialog,
    QDialog,
    QTextEdit,
    QDialogButtonBox,
    QSplitter,
)

from PyQt6.QtGui import QIcon

from status_help_view import build_status_help_view, get_status_help_file_path
from A_workflow_text_to_video import TextToVideoWorkflow
from worker_run_workflow_grok import GrokImageToVideoWorker, GrokTextToVideoWorker
from settings_manager import SettingsManager, WORKFLOWS_DIR, BASE_DIR, DATA_GENERAL_DIR, get_icon_path
from branding_config import OWNER_ZALO_URL
from voice_profiles import VOICE_JSON, VOICE_OPTIONS, get_voice_profile_text, normalize_locale
from gemini_automation import GeminiAutomation
from content_source import build_source_to_video_idea, fetch_url_text, limit_source_text, read_pdf_text


def _win_hidden_kwargs() -> dict:
    if os.name != "nt":
        return {}
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
        return {"startupinfo": si, "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    except Exception:
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}


def _icon(name: str) -> QIcon:
    if not name:
        return QIcon()
    path = get_icon_path(name)
    if os.path.isfile(path):
        return QIcon(path)
    return QIcon()


class _SelectAllHeader(QHeaderView):
    def __init__(self, panel: "StatusPanel"):
        super().__init__(Qt.Orientation.Horizontal, panel.table)
        self._panel = panel

        # A real widget (instead of paint-only) so the icon never "disappears"
        # due to style/paint quirks.
        self._btn = QToolButton(self.viewport())
        self._btn.setAutoRaise(True)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn.setIconSize(QSize(16, 16))
        self._btn.setFixedSize(22, 22)
        self._btn.clicked.connect(lambda _=False: self._panel._on_header_clicked(0))
        self.sync_from_panel()

        # Keep the button centered in section 0.
        try:
            self.sectionResized.connect(lambda *_: self._reposition_btn())
            self.sectionMoved.connect(lambda *_: self._reposition_btn())
            self.geometriesChanged.connect(self._reposition_btn)
        except Exception:
            pass

    def paintSection(self, painter: QPainter, rect, logicalIndex: int) -> None:
        super().paintSection(painter, rect, logicalIndex)
        if int(logicalIndex) != 0:
            return

        # Keep paint fallback (in case the button can't be created), but the
        # button is the primary UX.
        panel = self._panel
        ic = panel._cb_on if panel._select_all_checked else panel._cb_off
        if ic is not None and not ic.isNull():
            pm = ic.pixmap(16, 16)
            if not pm.isNull():
                try:
                    painter.save()
                    x = int(rect.x() + (rect.width() - pm.width()) / 2)
                    y = int(rect.y() + (rect.height() - pm.height()) / 2)
                    painter.drawPixmap(x, y, pm)
                finally:
                    try:
                        painter.restore()
                    except Exception:
                        pass
                return

        try:
            painter.save()
            side = 14
            x = int(rect.x() + (rect.width() - side) / 2)
            y = int(rect.y() + (rect.height() - side) / 2)
            painter.setPen(QColor("#10b981"))
            painter.setBrush(QBrush(QColor("#10b981") if panel._select_all_checked else QColor("transparent")))
            painter.drawRect(x, y, side, side)
            if panel._select_all_checked:
                painter.setPen(QColor("#ffffff"))
                painter.drawText(x, y - 1, side, side + 2, int(Qt.AlignmentFlag.AlignCenter), "✓")
        finally:
            try:
                painter.restore()
            except Exception:
                pass

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reposition_btn()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._reposition_btn()

    def _reposition_btn(self) -> None:
        try:
            # Use viewport-based coordinates; works correctly even if sections are moved.
            x0 = int(self.sectionViewportPosition(0))
            w0 = int(self.sectionSize(0))
            h = int(self.height())
        except Exception:
            return
        if w0 <= 0 or h <= 0:
            return
        x = int(x0 + (w0 - self._btn.width()) / 2)
        y = int((h - self._btn.height()) / 2)
        self._btn.move(x, y)

    def sync_from_panel(self) -> None:
        panel = self._panel
        panel._apply_checkbox_button_state(self._btn, panel._select_all_checked)
        self._btn.setVisible(True)
        self._reposition_btn()

    def mousePressEvent(self, event) -> None:
        try:
            idx = int(self.logicalIndexAt(event.pos()))
        except Exception:
            idx = -1
        if idx == 0:
            try:
                self._panel._on_header_clicked(0)
            except Exception:
                pass
            return
        super().mousePressEvent(event)


class _IdeaToVideoWorker(QThread):
    log_message = pyqtSignal(str)
    completed = pyqtSignal(dict)

    def __init__(
        self,
        project_name: str,
        idea_text: str,
        scene_count: int,
        style: str,
        language: str,
        source_mode: str = "manual",
        source_kind: str = "auto",
        source_url: str = "",
        source_pdf_path: str = "",
        output_mode: str = "video",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._project_name = str(project_name or "default_project")
        self._idea_text = str(idea_text or "")
        self._scene_count = int(scene_count or 1)
        self._style = str(style or "3d_Pixar")
        self._language = str(language or "Tiếng Việt (vi-VN)")
        self._source_mode = str(source_mode or "manual").strip()
        self._source_kind = str(source_kind or "auto").strip()
        self._source_url = str(source_url or "").strip()
        self._source_pdf_path = str(source_pdf_path or "").strip()
        self._output_mode = "storytelling_image" if str(output_mode or "").strip() == "storytelling_image" else "video"
        self._stop_requested = False

    def stop(self) -> None:
        self._stop_requested = True

    def run(self) -> None:
        def _log(message: str) -> None:
            self.log_message.emit(str(message or ""))

        def _should_stop() -> bool:
            return bool(self._stop_requested)

        try:
            from idea_to_video import idea_to_video_workflow

            effective_idea = self._idea_text
            if self._source_mode == "pdf":
                _log(f"📄 Đang đọc nội dung từ PDF: {self._source_pdf_path}")
                source_text = read_pdf_text(self._source_pdf_path)
                _log(f"✅ Đã đọc nội dung PDF: {len(source_text)} ký tự")
                effective_idea = build_source_to_video_idea(
                    source_text=source_text,
                    source_mode="pdf",
                    source_kind=self._source_kind,
                    source_url=self._source_pdf_path,
                    extra_note=self._idea_text,
                )
            elif self._source_mode == "link":
                _log(f"🔗 Đang đọc nội dung từ link: {self._source_url}")
                source_text = fetch_url_text(self._source_url)
                _log(f"✅ Đã đọc nội dung nguồn: {len(source_text)} ký tự")
                effective_idea = build_source_to_video_idea(
                    source_text=source_text,
                    source_mode="link",
                    source_kind=self._source_kind,
                    source_url=self._source_url,
                    extra_note=self._idea_text,
                )
            elif self._source_kind != "auto":
                effective_idea = build_source_to_video_idea(
                    source_text=limit_source_text(self._idea_text),
                    source_mode="manual",
                    source_kind=self._source_kind,
                )

            result = idea_to_video_workflow(
                self._project_name,
                effective_idea,
                scene_count=self._scene_count,
                style=self._style,
                language=self._language,
                log_callback=_log,
                stop_check=_should_stop,
            )
            if not isinstance(result, dict):
                result = {"success": False, "message": "Kết quả Idea to Video không hợp lệ."}
            result["_output_mode"] = self._output_mode
            self.completed.emit(result)
        except BaseException as exc:
            self.completed.emit({"success": False, "message": f"Lỗi Idea to Video: {exc}"})

def _clamp_copy_strength(value) -> int:
    try:
        strength = int(value)
    except Exception:
        strength = 100
    return max(50, min(100, strength))


class _GeminiCloneWorker(QThread):
    log_message = pyqtSignal(str)
    completed = pyqtSignal(dict)

    def __init__(
        self,
        video_path: str,
        profile_path: str,
        target_language: str,
        bootstrap_url: str = "",
        style: str = "Tự động nhận diện",
        copy_strength: int = 100,
        user_edit_instruction: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.video_path = video_path
        self.profile_path = profile_path
        self.target_language = str(target_language or "en-US")
        self.bootstrap_url = str(bootstrap_url or "")
        self.style = str(style or "Tự động nhận diện")
        self.copy_strength = _clamp_copy_strength(copy_strength)
        self.user_edit_instruction = str(user_edit_instruction or "").strip()

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        auto = None
        try:
            auto = GeminiAutomation(
                profile_path=self.profile_path,
                headless=False,
                bootstrap_url=self.bootstrap_url,
                log_callback=self.log_message.emit,
            )
            loop.run_until_complete(asyncio.wait_for(auto.start(), timeout=25))
            self.log_message.emit(f"🎬 Đang phân tích video: {os.path.basename(self.video_path)}...")
            result = loop.run_until_complete(
                asyncio.wait_for(
                    auto.analyze_video_v2(
                        self.video_path,
                        target_language=self.target_language,
                        style=self.style,
                        copy_strength=self.copy_strength,
                        user_edit_instruction=self.user_edit_instruction,
                    ),
                    timeout=360,
                )
            )
            self.completed.emit({"success": True, "data": result})
        except Exception as e:
            self.completed.emit({"success": False, "message": str(e)})
        finally:
            try:
                if auto is not None:
                    loop.run_until_complete(asyncio.wait_for(auto.close(), timeout=10))
            except Exception:
                pass
            try:
                pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            try:
                loop.run_until_complete(asyncio.sleep(0))
            except Exception:
                pass
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            try:
                asyncio.set_event_loop(None)
            except Exception:
                pass
            loop.close()

import asyncio


class _StorytellingExportWorker(QThread):
    log_message = pyqtSignal(str)
    completed = pyqtSignal(dict)

    def __init__(
        self,
        items: list[dict],
        output_dir: str,
        voice_key: str,
        tts_provider: str,
        aspect_ratio: str,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._items = list(items or [])
        self._output_dir = str(output_dir or "")
        self._voice_key = str(voice_key or "None_NoVoice")
        self._tts_provider = str(tts_provider or "auto")
        self._aspect_ratio = str(aspect_ratio or "9:16")

    def run(self) -> None:
        try:
            from storytelling_exporter import export_storytelling_video

            out_path = export_storytelling_video(
                self._items,
                self._output_dir,
                voice_key=self._voice_key,
                tts_provider=self._tts_provider,
                aspect_ratio=self._aspect_ratio,
                log_callback=self.log_message.emit,
            )
            self.completed.emit({"success": True, "path": out_path})
        except BaseException as exc:
            self.completed.emit({"success": False, "message": str(exc)})


class StatusPanel(QWidget):
    COL_CHECK = 0
    COL_STT = 1
    COL_VIDEO = 2
    COL_STATUS = 3
    COL_MODE = 4
    COL_PROMPT = 5

    MODE_TEXT_TO_VIDEO = "text_to_video"
    MODE_IMAGE_TO_VIDEO_SINGLE = "image_to_video_single"
    MODE_IMAGE_TO_VIDEO_START_END = "image_to_video_start_end"
    MODE_CHARACTER_SYNC = "character_sync"
    MODE_CREATE_IMAGE_PROMPT = "create_image_prompt"
    MODE_CREATE_IMAGE_REFERENCE = "create_image_reference"
    MODE_GROK_TEXT_TO_VIDEO = "grok_text_to_video"
    MODE_GROK_IMAGE_TO_VIDEO = "grok_image_to_video"
    MODE_COPY_VIDEO = "copy_video"
    AUTO_RETRY_ERROR_CODES = {"403", "13", "500"}
    AUTO_RETRY_MAX_PER_ROW = 1

    requestStop = pyqtSignal()
    runStateChanged = pyqtSignal(bool)
    titleChanged = pyqtSignal(str)
    queueJobsRequested = pyqtSignal(list)
    thumbnailReady = pyqtSignal(str, str)

    def __init__(self, config, parent: QWidget | None = None):
        super().__init__(parent)
        self._cfg = config
        self._running = False
        self._workflow: TextToVideoWorkflow | None = None
        self._workflows: list[QThread] = []
        self._idea_worker: _IdeaToVideoWorker | None = None
        self._clone_worker: _GeminiCloneWorker | None = None
        self._retry_mode_queue: list[tuple[str, list[int]]] = []
        self._global_stop_requested = False
        self._stop_poll_attempts = 0
        self._active_queue_rows: set[int] = set()
        self._awaiting_completion_confirmation = False
        self._completion_poll_scheduled = False
        self._completion_poll_attempts = 0
        self._loading_status_snapshot = False
        self._status_loaded = False
        self._thumb_jobs_inflight: set[str] = set()
        self._thumb_attempted_mtime: dict[str, float] = {}
        self.thumbnailReady.connect(self._on_thumbnail_ready)

        self._cb_off = _icon("checkbox-unchecked.png")
        self._cb_on = _icon("checkbox-checked.png")
        self._use_checkbox_icon = bool((self._cb_off is not None and not self._cb_off.isNull()) and (self._cb_on is not None and not self._cb_on.isNull()))
        self._select_all_checked = False

        layout = QVBoxLayout(self)
        # Keep panel padding but bring the table closer to the toolbar.
        layout.setContentsMargins(0, 0, 0, 12)
        layout.setSpacing(6)

        # Toolbar
        tb = QHBoxLayout()
        tb.setContentsMargins(0, 0, 0, 0)
        tb.setSpacing(8)
        self.btn_join_video = QPushButton("Nối video")
        self.btn_join_video.setProperty("topRow", True)
        self.btn_join_video.setObjectName("TopAction")
        self.btn_join_video.clicked.connect(self._on_join_video_clicked)
        tb.addWidget(self.btn_join_video)

        self.btn_retry = QPushButton("Tạo lại video")
        self.btn_retry.setProperty("topRow", True)
        self.btn_retry.setObjectName("TopAction")
        self.btn_retry.clicked.connect(self._on_retry_selected_clicked)
        tb.addWidget(self.btn_retry)

        self.btn_retry_failed = QPushButton("Tạo lại video lỗi")
        self.btn_retry_failed.setProperty("topRow", True)
        self.btn_retry_failed.setObjectName("TopAction")
        self.btn_retry_failed.clicked.connect(self._on_retry_failed_clicked)
        tb.addWidget(self.btn_retry_failed)

        self.btn_cut_last = QPushButton("Cắt ảnh cuối")
        self.btn_cut_last.setProperty("topRow", True)
        self.btn_cut_last.setObjectName("TopAction")
        self.btn_cut_last.clicked.connect(self._on_cut_last_clicked)
        tb.addWidget(self.btn_cut_last)

        self.btn_del = QPushButton("Xóa kết quả")
        self.btn_del.setProperty("topRow", True)
        self.btn_del.setObjectName("DangerSoft")
        self.btn_del.clicked.connect(self.delete_selected_rows)
        tb.addWidget(self.btn_del)

        self.btn_zalo = QPushButton("Nhóm Zalo")
        self.btn_zalo.setObjectName("Zalo")
        self.btn_zalo.setProperty("topRow", True)
        try:
            ic = _icon("zalo.png")
            if not ic.isNull():
                self.btn_zalo.setIcon(ic)
        except Exception:
            pass
        self.btn_zalo.clicked.connect(self._open_zalo_group)
        tb.addWidget(self.btn_zalo)

        tb.addStretch(1)
        layout.addLayout(tb)

        summary_bar = QHBoxLayout()
        summary_bar.setContentsMargins(0, 0, 0, 2)
        summary_bar.setSpacing(8)
        self.lbl_status_summary = QLabel("")
        self.lbl_status_summary.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_status_summary.setStyleSheet("font-weight:700; color: #1f2d48;")
        summary_bar.addWidget(self.lbl_status_summary)
        self.btn_open_guide = QPushButton("Xem Hướng Dẫn Sử Dụng TOOL")
        self.btn_open_guide.setProperty("topRow", True)
        self.btn_open_guide.setObjectName("TopAction")
        self.btn_open_guide.clicked.connect(self._open_usage_guide_file)
        summary_bar.addWidget(self.btn_open_guide)
        summary_bar.addStretch(1)
        layout.addLayout(summary_bar)

        # Main content area: show guide when empty; show status table when there are rows.
        self._body_splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(self._body_splitter, 1)

        self._stack = QStackedWidget()
        self._body_splitter.addWidget(self._stack)

        self._help_view = self._build_help_view()
        self._stack.addWidget(self._help_view)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Chọn", "STT", "Video", "Trạng thái", "Mode", "Prompt"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.table.setAlternatingRowColors(True)
        try:
            self.table.verticalHeader().setDefaultSectionSize(120)
        except Exception:
            pass

        hdr = _SelectAllHeader(self)
        self.table.setHorizontalHeader(hdr)
        try:
            hdr.setFixedHeight(34)
        except Exception:
            pass
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        # Column sizes: FIXED PIXELS (no ratio / no stretch)
        # Apply AFTER custom header is installed (Qt can reset widths when header changes).
        self._col_widths = {
            self.COL_CHECK: 32,   # checkbox
            self.COL_STT: 46,     # STT
            self.COL_VIDEO: 120,  # Video
            self.COL_STATUS: 128, # Trạng thái
            self.COL_MODE: 172,   # Mode
            self.COL_PROMPT: 220, # Prompt
        }

        def _apply_col_widths() -> None:
            try:
                for i, w in self._col_widths.items():
                    hdr.resizeSection(int(i), int(w))
            except Exception:
                pass

        try:
            QTimer.singleShot(0, _apply_col_widths)
        except Exception:
            _apply_col_widths()

        # Header checkbox is painted centered by _SelectAllHeader.
        try:
            h0 = self.table.horizontalHeaderItem(0)
            if h0 is not None:
                h0.setText("")
        except Exception:
            pass
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.itemChanged.connect(self._on_table_item_changed)
        self._stack.addWidget(self.table)

        self._log_group = QGroupBox("Nhật ký chạy")
        self._log_group.setStyleSheet("QGroupBox{font-weight:800;}")
        log_layout = QVBoxLayout(self._log_group)
        log_layout.setContentsMargins(8, 8, 8, 8)
        log_layout.setSpacing(6)

        self._run_log = QPlainTextEdit()
        self._run_log.setReadOnly(True)
        self._run_log.setMinimumHeight(78)
        self._run_log.setStyleSheet("background:#ffffff; color:#1e293b; border:1px solid #c8d7f2;")
        log_layout.addWidget(self._run_log)

        self._body_splitter.addWidget(self._log_group)
        try:
            self._body_splitter.setStretchFactor(0, 4)
            self._body_splitter.setStretchFactor(1, 1)
            QTimer.singleShot(0, lambda: self._body_splitter.setSizes([640, 90]))
        except Exception:
            pass

        self._account_group = QGroupBox("Thông tin tài khoản")
        self._account_group.setStyleSheet(
            "QGroupBox{font-weight:800; color:#1f2d48; border:1px solid #c8d7f2; border-radius:12px; margin-top:6px; background:#eaf2ff;}"
            "QGroupBox::title{subcontrol-origin:margin; left:15px; padding:0 8px; color:#1f2d48;}"
        )
        self._account_group.setMinimumHeight(72)
        self._account_group.setMaximumHeight(86)
        account_layout = QHBoxLayout(self._account_group)
        account_layout.setContentsMargins(12, 8, 12, 8)
        account_layout.setSpacing(18)

        lb_account = QLabel("Tài khoản:")
        lb_account.setStyleSheet("font-weight:800; color:#1f2d48;")
        self._account_value = QLabel("Default")
        self._account_value.setStyleSheet("color:#1f2d48; font-weight: 600;")

        lb_type = QLabel("Loại:")
        lb_type.setStyleSheet("font-weight:800; color:#1f2d48;")
        self._account_type_value = QLabel("VIP1")
        self._account_type_value.setStyleSheet("color:#1f2d48; font-weight: 600;")

        lb_expiry = QLabel("Hết hạn:")
        lb_expiry.setStyleSheet("font-weight:800; color:#1f2d48;")
        self._account_expiry_value = QLabel("-")
        self._account_expiry_value.setStyleSheet("color:#1f2d48; font-weight: 600;")

        account_layout.addWidget(lb_account)
        account_layout.addWidget(self._account_value)
        account_layout.addSpacing(8)
        account_layout.addWidget(lb_type)
        account_layout.addWidget(self._account_type_value)
        account_layout.addSpacing(8)
        account_layout.addWidget(lb_expiry)
        account_layout.addWidget(self._account_expiry_value)
        account_layout.addStretch(1)

        layout.addWidget(self._account_group, 0)

        self._update_empty_state()
        self._ensure_status_snapshot_loaded()
        self._update_status_summary()
        self._refresh_account_info()

    def _format_expiry_date(self, raw_value) -> str:
        try:
            val = int(raw_value or 0)
        except Exception:
            val = 0
        if val <= 0:
            return "-"
        try:
            dt = datetime.fromtimestamp(val)
            return dt.strftime("%d/%m/%Y")
        except Exception:
            return "-"

    def _extract_license_account_and_type(self, state_data: dict) -> tuple[str, str]:
        account_value = ""
        type_value = ""
        if not isinstance(state_data, dict):
            return "", ""

        raw_features = state_data.get("features")
        payload = None
        if isinstance(raw_features, dict):
            payload = raw_features
        elif isinstance(raw_features, str):
            txt = raw_features.strip()
            if txt:
                try:
                    decoded = json.loads(txt)
                    if isinstance(decoded, dict):
                        payload = decoded
                except Exception:
                    payload = None

        if isinstance(payload, dict):
            account_value = str(payload.get("account") or "").strip()
            type_value = str(payload.get("type") or payload.get("account_type") or "").strip()

        if not account_value:
            account_value = str(state_data.get("account") or "").strip()
        if not type_value:
            type_value = str(state_data.get("type") or state_data.get("account_type") or "").strip()

        return account_value, type_value

    def _refresh_account_info(self) -> None:
        account_value = "Default"
        type_value = "VIP1"
        expiry_value = "-"

        try:
            state_path = Path(DATA_GENERAL_DIR) / "license_state.json"
            if state_path.exists():
                with open(state_path, "r", encoding="utf-8") as f:
                    state_data = json.load(f)
                if isinstance(state_data, dict):
                    parsed_account, parsed_type = self._extract_license_account_and_type(state_data)
                    if parsed_account:
                        account_value = parsed_account
                    if parsed_type:
                        type_value = parsed_type
                    expiry_value = self._format_expiry_date(state_data.get("expires_at"))
        except Exception:
            pass

        try:
            self._account_value.setText(account_value)
            self._account_type_value.setText(type_value)
            self._account_expiry_value.setText(expiry_value)
        except Exception:
            pass

    def _append_run_log(self, message: str) -> None:
        if self._run_log is None:
            return
        text = str(message or "")
        if "Đang chờ" in text and "video hoàn thành" in text:
            waiting = self._count_waiting_completion_on_table()
            if waiting <= 0:
                return
            text = f"⏳ Đang chờ {waiting} video hoàn thành..."
        ts = datetime.now().strftime("%H:%M:%S")
        self._run_log.appendPlainText(f"[{ts}] {text}")

    def _open_zalo_group(self) -> None:
        url = str(OWNER_ZALO_URL or "").strip()
        if not url:
            QMessageBox.warning(self, "Nhóm Zalo", "Chưa cấu hình link nhóm Zalo.")
            return
        ok = QDesktopServices.openUrl(QUrl(url))
        if not ok:
            QMessageBox.warning(self, "Nhóm Zalo", f"Không mở được liên kết:\n{url}")

    def _open_usage_guide_file(self) -> None:
        try:
            guide_path = get_status_help_file_path()
            ok = QDesktopServices.openUrl(QUrl.fromLocalFile(str(guide_path)))
            if not ok:
                QMessageBox.warning(self, "Hướng dẫn", f"Không mở được file hướng dẫn:\n{guide_path}")
        except Exception as exc:
            QMessageBox.warning(self, "Hướng dẫn", f"Không mở được file hướng dẫn: {exc}")

    def append_run_log(self, message: str) -> None:
        self._append_run_log(message)

    def _count_waiting_completion_on_table(self) -> int:
        # Theo yêu cầu: không tính video đang chờ tạo (PENDING).
        count = 0
        for r in range(self.table.rowCount()):
            code = self._status_code(r)
            if code in {"TOKEN", "REQUESTED", "ACTIVE", "DOWNLOADING"}:
                count += 1
        return count

    def _build_help_view(self) -> QWidget:
        return build_status_help_view()

    def _update_empty_state(self) -> None:
        try:
            empty = int(self.table.rowCount() or 0) <= 0
        except Exception:
            empty = True
        try:
            self._stack.setCurrentIndex(0 if empty else 1)
        except Exception:
            pass
        try:
            has_log = bool(str(self._run_log.toPlainText() or "").strip()) if self._run_log is not None else False
            show_log = bool((not empty) or self.isRunning() or has_log)
            self._log_group.setVisible(show_log)
        except Exception:
            pass

    def _row_checked(self, row: int) -> bool:
        it = self.table.item(int(row), self.COL_CHECK)
        if it is None:
            return False
        try:
            return bool(it.data(Qt.ItemDataRole.UserRole) is True)
        except Exception:
            return False

    def _set_row_checked(self, row: int, checked: bool) -> None:
        r = int(row)
        it = self.table.item(r, self.COL_CHECK)
        if it is None:
            return
        want = bool(checked)
        try:
            it.setData(Qt.ItemDataRole.UserRole, want)
        except Exception:
            pass
        # Update the visual widget if present
        w = self.table.cellWidget(r, self.COL_CHECK)
        if w is not None:
            btn = getattr(w, "_cb_btn", None)
            if isinstance(btn, QToolButton):
                self._apply_checkbox_button_state(btn, want)

    def _apply_checkbox_button_state(self, btn: QToolButton, checked: bool) -> None:
        if self._use_checkbox_icon:
            ic = self._cb_on if bool(checked) else self._cb_off
            if ic is not None and not ic.isNull():
                btn.setText("")
                btn.setStyleSheet("")
                btn.setIcon(ic)
                return

        btn.setIcon(QIcon())
        btn.setText("✓" if bool(checked) else "")
        if checked:
            btn.setStyleSheet(
                "QToolButton {border: 1px solid #16a34a; border-radius: 3px; background: #16a34a; color: white; font-weight: 800;}"
            )
        else:
            btn.setStyleSheet(
                "QToolButton {border: 1px solid #16a34a; border-radius: 3px; background: transparent; color: #16a34a; font-weight: 800;}"
            )

    def _toggle_row_checked(self, row: int) -> None:
        self._set_row_checked(int(row), not self._row_checked(int(row)))
        self._sync_select_all_header()

    def _sync_select_all_header(self) -> None:
        # Update header icon state based on all rows.
        total = int(self.table.rowCount() or 0)
        if total <= 0:
            all_checked = False
        else:
            all_checked = True
            for r in range(total):
                if not self._row_checked(r):
                    all_checked = False
                    break

        self._select_all_checked = bool(all_checked)
        try:
            hdr = self.table.horizontalHeader()
            if isinstance(hdr, _SelectAllHeader):
                hdr.sync_from_panel()
            else:
                hdr.viewport().update()
        except Exception:
            pass

    def _on_header_clicked(self, section: int) -> None:
        if int(section) != 0:
            return
        # Toggle select-all
        want = not bool(self._select_all_checked)
        for r in range(self.table.rowCount()):
            self._set_row_checked(r, want)
        self._sync_select_all_header()

    def isRunning(self) -> bool:
        try:
            wf_running = any(bool(wf and wf.isRunning()) for wf in list(self._workflows))
            idea_running = bool(self._idea_worker and self._idea_worker.isRunning())
            clone_running = bool(self._clone_worker and self._clone_worker.isRunning())
            return bool(wf_running or idea_running or clone_running)
        except Exception:
            return False

    def get_running_video_count(self) -> int:
        if not self.isRunning():
            return 0
        running_codes = {"TOKEN", "REQUESTED", "ACTIVE", "DOWNLOADING"}
        count = 0
        rows = sorted(int(r) for r in list(self._active_queue_rows)) if self._active_queue_rows else list(range(self.table.rowCount()))
        for r in rows:
            try:
                if self._status_code(r) in running_codes:
                    count += 1
            except Exception:
                pass
        return int(count)

    def stop(self) -> None:
        self._global_stop_requested = True
        self._retry_mode_queue = []
        self._active_queue_rows.clear()
        self._awaiting_completion_confirmation = False
        self._completion_poll_scheduled = False
        self._completion_poll_attempts = 0
        self._append_run_log("🛑 Đang dừng workflow...")
        if self._idea_worker is not None:
            try:
                self._idea_worker.stop()
                self._append_run_log("🛑 Đang dừng Idea to Video...")
            except Exception:
                pass
        if self._clone_worker is not None:
            try:
                self._clone_worker.requestInterruption()
                self._append_run_log("ðŸ›‘ Äang dá»«ng Copy Video...")
            except Exception:
                pass
        if self._workflow is not None:
            try:
                self._workflow.stop()
                self._workflow.requestInterruption()
            except Exception:
                pass
        for wf in list(self._workflows):
            try:
                wf.stop()
                wf.requestInterruption()
            except Exception:
                pass
        self._mark_active_rows_stopped()
        self._refresh_pending_positions()
        self.requestStop.emit()
        try:
            self._stop_poll_attempts = 0
            QTimer.singleShot(150, self._poll_stop_state)
        except Exception:
            pass

    def stop(self) -> None:
        self._global_stop_requested = True
        self._retry_mode_queue = []
        self._active_queue_rows.clear()
        self._awaiting_completion_confirmation = False
        self._completion_poll_scheduled = False
        self._completion_poll_attempts = 0
        self._append_run_log("🛑 Đang dừng workflow...")
        if self._idea_worker is not None:
            try:
                self._idea_worker.stop()
                self._append_run_log("🛑 Đang dừng Idea to Video...")
            except Exception:
                pass
        if self._clone_worker is not None:
            try:
                self._clone_worker.requestInterruption()
                self._append_run_log("🛑 Đang dừng Sao chép video...")
            except Exception:
                pass
        if self._workflow is not None:
            try:
                self._workflow.stop()
                self._workflow.requestInterruption()
            except Exception:
                pass
        for wf in list(self._workflows):
            try:
                wf.stop()
                wf.requestInterruption()
            except Exception:
                pass
        self._mark_active_rows_stopped()
        self._refresh_pending_positions()
        self.requestStop.emit()
        try:
            self._stop_poll_attempts = 0
            QTimer.singleShot(150, self._poll_stop_state)
        except Exception:
            pass

    def shutdown(self, timeout_ms: int = 2200) -> None:
        self._active_queue_rows.clear()
        self._awaiting_completion_confirmation = False
        self._completion_poll_scheduled = False
        self._completion_poll_attempts = 0
        idea = self._idea_worker
        clone = self._clone_worker
        if idea is not None:
            try:
                idea.stop()
                idea.requestInterruption()
            except Exception:
                pass
        if clone is not None:
            try:
                clone.requestInterruption()
            except Exception:
                pass

        workflows = list(self._workflows)
        for wf in workflows:
            try:
                wf.stop()
                wf.requestInterruption()
            except Exception:
                pass

        for thread_obj in ([idea, clone] + workflows):
            if thread_obj is None:
                continue
            try:
                if thread_obj.isRunning():
                    thread_obj.wait(max(200, int(timeout_ms // 2)))
                if thread_obj.isRunning():
                    thread_obj.terminate()
                    thread_obj.wait(400)
            except Exception:
                pass

        self._idea_worker = None
        self._clone_worker = None
        self._workflow = None
        self._workflows = []

    def _poll_stop_state(self) -> None:
        idea = self._idea_worker
        if idea is not None:
            try:
                if not idea.isRunning():
                    self._idea_worker = None
            except Exception:
                self._idea_worker = None
        clone = self._clone_worker
        if clone is not None:
            try:
                if not clone.isRunning():
                    self._clone_worker = None
            except Exception:
                self._clone_worker = None

        alive_workflows: list[QThread] = []
        for wf in list(self._workflows):
            try:
                if wf and wf.isRunning():
                    alive_workflows.append(wf)
            except Exception:
                pass
        self._workflows = alive_workflows
        self._workflow = self._workflows[-1] if self._workflows else None

        wf = self._workflow
        if (not self._workflows) and self._idea_worker is None and self._clone_worker is None:
            self.runStateChanged.emit(False)
            return

        if not self._workflows:
            self._stop_poll_attempts += 1
            if self._stop_poll_attempts >= 40:
                self.runStateChanged.emit(False)
                return
            try:
                QTimer.singleShot(200, self._poll_stop_state)
            except Exception:
                pass
            return

        try:
            if not wf.isRunning():
                self._finalize_stop_if_finished()
                return
        except Exception:
            self._finalize_stop_if_finished()
            return

        self._stop_poll_attempts += 1
        if self._stop_poll_attempts >= 40:
            self._append_run_log("⚠️ Workflow chưa thoát kịp, UI vẫn hoạt động và sẽ nhận trạng thái dừng.")
            self._workflow = None
            self._workflows = []
            self.runStateChanged.emit(False)
            return

        try:
            QTimer.singleShot(200, self._poll_stop_state)
        except Exception:
            pass

    def _finalize_stop_if_finished(self) -> None:
        alive_workflows: list[QThread] = []
        for wf in list(self._workflows):
            try:
                if wf and wf.isRunning():
                    alive_workflows.append(wf)
            except Exception:
                pass
        self._workflows = alive_workflows
        self._workflow = self._workflows[-1] if self._workflows else None
        if not self._workflows:
            self.runStateChanged.emit(False)
            return
        self._append_run_log("✅ Đã dừng workflow")

    def _mark_rows_pending(self, rows: list[int]) -> None:
        for r in rows:
            self._set_status_code(int(r), "PENDING")
        self._refresh_pending_positions()

    def _is_storytelling_row(self, row: int) -> bool:
        payload = self._row_mode_payload(int(row))
        return str(payload.get("source_type") or "").strip() == "storytelling_image"

    def _parse_storytelling_prompt_object(self, prompt_text: str) -> dict:
        raw = str(prompt_text or "").strip().lstrip("\ufeff")
        if not raw:
            return {}
        if raw.startswith("```"):
            parts = raw.split("```")
            if len(parts) >= 2:
                raw = parts[1].strip()
                if raw.lower().startswith("json"):
                    raw = raw[4:].strip()
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def _clean_storytelling_narration_line(self, value: str) -> str:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        text = re.sub(r"^\[[^\]]{1,60}:\s*", "", text).strip()
        text = text.strip("[] \t\r\n")
        return text.strip(" \"'")

    def _prompt_value_to_phrase(self, value, max_chars: int = 260) -> str:
        if value in (None, "", [], {}):
            return ""
        if isinstance(value, list):
            text = ", ".join(
                part for part in (self._prompt_value_to_phrase(item, max_chars=max_chars) for item in value)
                if part
            )
        elif isinstance(value, dict):
            parts: list[str] = []
            for key, item in value.items():
                item_text = self._prompt_value_to_phrase(item, max_chars=max_chars)
                if item_text:
                    parts.append(f"{key}: {item_text}")
            text = ", ".join(parts)
        else:
            text = str(value or "")
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > max_chars:
            text = text[:max_chars].rstrip(" ,.;:") + "..."
        return text

    def _compact_prompt_json_value(self, value, max_chars: int = 1400) -> str:
        if value in (None, "", [], {}):
            return ""
        try:
            text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            text = str(value)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > max_chars:
            text = text[:max_chars].rstrip(" ,.;:") + "..."
        return text

    def _describe_idea_character_lock(self, value, max_chars: int = 1600) -> str:
        if not isinstance(value, dict):
            return self._compact_prompt_json_value(value, max_chars=max_chars)

        chunks: list[str] = []
        fields = [
            "name", "species", "gender", "age", "body_build", "body_metrics",
            "face_shape", "hair", "skin_or_fur_color", "signature_feature",
            "outfit_top", "outfit_bottom", "helmet_or_hat", "shoes_or_footwear",
            "props", "position", "orientation", "pose", "expression", "action_flow",
        ]
        for key, data in value.items():
            if not isinstance(data, dict):
                text = self._prompt_value_to_phrase(data, max_chars=220)
                if text:
                    chunks.append(f"{key}: {text}")
                continue
            label = str(data.get("name") or data.get("id") or key).strip()
            details: list[str] = []
            for field in fields:
                field_text = self._prompt_value_to_phrase(data.get(field), max_chars=220)
                if field_text:
                    details.append(f"{field.replace('_', ' ')}: {field_text}")
            if details:
                chunks.append(f"{label}: " + ", ".join(details))

        text = "; ".join(chunks).strip()
        if len(text) > max_chars:
            text = text[:max_chars].rstrip(" ,.;:") + "..."
        return text

    def _describe_idea_background_lock(self, value, max_chars: int = 1200) -> str:
        if not isinstance(value, dict):
            return self._compact_prompt_json_value(value, max_chars=max_chars)

        chunks: list[str] = []
        fields = ["name", "setting", "scenery", "props", "lighting", "weather", "mood", "layout"]
        for key, data in value.items():
            if not isinstance(data, dict):
                text = self._prompt_value_to_phrase(data, max_chars=220)
                if text:
                    chunks.append(f"{key}: {text}")
                continue
            label = str(data.get("name") or data.get("id") or key).strip()
            details = [
                f"{field.replace('_', ' ')}: {self._prompt_value_to_phrase(data.get(field), max_chars=220)}"
                for field in fields
                if self._prompt_value_to_phrase(data.get(field), max_chars=220)
            ]
            if details:
                chunks.append(f"{label}: " + ", ".join(details))

        text = "; ".join(chunks).strip()
        if len(text) > max_chars:
            text = text[:max_chars].rstrip(" ,.;:") + "..."
        return text

    def _describe_idea_camera(self, value, max_chars: int = 650) -> str:
        if not isinstance(value, dict):
            return self._prompt_value_to_phrase(value, max_chars=max_chars)
        parts: list[str] = []
        for key in ("framing", "angle", "movement", "focus", "lens"):
            text = self._prompt_value_to_phrase(value.get(key), max_chars=180)
            if text:
                parts.append(f"{key}: {text}")
        fallback = self._compact_prompt_json_value(value, max_chars=max_chars)
        text = "; ".join(parts).strip() or fallback
        if len(text) > max_chars:
            text = text[:max_chars].rstrip(" ,.;:") + "..."
        return text

    def _idea_dialogue_lines(self, prompt_obj: dict) -> list[dict]:
        lines: list[dict] = []
        dialogue = prompt_obj.get("dialogue") if isinstance(prompt_obj, dict) else None
        if not isinstance(dialogue, list):
            return lines
        for line in dialogue:
            if isinstance(line, dict):
                line_text = str(line.get("line") or line.get("text") or line.get("content") or line.get("dialogue") or "").strip()
                speaker = str(line.get("speaker") or "NARRATOR").strip() or "NARRATOR"
                voice = str(line.get("voice") or "").strip()
            else:
                line_text = str(line or "").strip()
                speaker = "NARRATOR"
                voice = ""
            line_text = self._clean_storytelling_narration_line(line_text)
            if line_text:
                lines.append({"speaker": speaker, "voice": voice, "line": line_text})
        return lines

    def _describe_idea_foley(self, value) -> tuple[str, str]:
        if not isinstance(value, dict):
            text = self._prompt_value_to_phrase(value, max_chars=700)
            return text, ""
        ambience = self._prompt_value_to_phrase(value.get("ambience"), max_chars=360)
        fx = self._prompt_value_to_phrase(value.get("fx"), max_chars=360)
        music = self._prompt_value_to_phrase(value.get("music"), max_chars=220)
        parts = []
        if ambience:
            parts.append(f"ambience: {ambience}")
        if fx:
            parts.append(f"sound effects: {fx}")
        return "; ".join(parts).strip(), music

    def _idea_video_prompt_from_prompt_text(
        self,
        prompt_text: str,
        index: int = 1,
        voice_profile_text: str = "",
    ) -> str:
        prompt_obj = self._parse_storytelling_prompt_object(prompt_text)
        if not prompt_obj:
            base = re.sub(r"\s+", " ", str(prompt_text or "")).strip()
            strict = (
                "STRICT RULE: ZERO visible text in the video. No letters, numbers, subtitles, "
                "captions, logos, watermarks, or UI elements anywhere in the frame. "
                "STRICT AUDIO RULE: narrator audio is voice-over only; do not show the narrator "
                "and do not create lip-sync unless a visible speaking character is explicitly requested. "
                "STRICTLY NO BGM; generate NO music or soundtrack unless the prompt explicitly lists one."
            )
            return "\n".join(part for part in [base, strict] if part).strip()

        visual_style = str(prompt_obj.get("visual_style") or "").strip()
        summary = str(prompt_obj.get("summary") or "").strip()
        character_lock = self._describe_idea_character_lock(prompt_obj.get("character_lock"))
        background_lock = self._describe_idea_background_lock(prompt_obj.get("background_lock"))
        camera = self._describe_idea_camera(prompt_obj.get("camera"))
        foley, music = self._describe_idea_foley(prompt_obj.get("foley_and_ambience"))
        dialogue_lines = self._idea_dialogue_lines(prompt_obj)
        narration_text = " ".join(line["line"] for line in dialogue_lines).strip() or summary
        narration_text = re.sub(r"\s+", " ", narration_text).strip()
        narration_for_prompt = narration_text.replace('"', "'")
        voice_hint = ""
        if dialogue_lines:
            voice_hint = str(dialogue_lines[0].get("voice") or "").strip()
        if str(voice_profile_text or "").strip():
            voice_hint = str(voice_profile_text or "").strip()
        audio_voice = f"NARRATOR ({voice_hint}, voice-over)" if voice_hint else "NARRATOR (clear natural voice-over)"
        scene_id = str(prompt_obj.get("scene_id") or index).strip() or str(index)

        video_parts = []
        if visual_style:
            video_parts.append(visual_style.rstrip(".") + ".")
        if summary:
            video_parts.append(summary.rstrip(".") + ".")
        if character_lock:
            video_parts.append(f"Characters and consistency lock: {character_lock}.")
        if background_lock:
            video_parts.append(f"Setting/background: {background_lock}.")
        if camera:
            video_parts.append(f"Camera: {camera}.")
        video_parts.append(
            "Create a complete 8-second story beat with a clear beginning, middle, and ending; "
            "keep motion natural, emotionally readable, and consistent with the source story."
        )

        audio_parts = []
        if narration_for_prompt:
            audio_parts.append(f'Audio: {audio_voice} says "{narration_for_prompt}".')
        else:
            audio_parts.append("Audio: no voice.")
        if foley:
            audio_parts.append(f"ASMR: {foley}.")
        if music and music.lower() not in {"none", "no", "no music", "silent", "silence", "n/a"}:
            audio_parts.append(f"BGM: {music}.")
        else:
            audio_parts.append("BGM: no music.")

        strict_rules = [
            "STRICT AUDIO RULE: NARRATOR is voice-over only. Never render the narrator visually and never trigger lip-sync for narrator dialogue.",
            "STRICT LIP-SYNC RULE: unless a visible character is explicitly tagged as speaking in the scene, all visible characters keep their mouths closed with ZERO lip movement.",
            "STRICT CHARACTER RULE: characters must match the character consistency lock exactly; do not redesign faces, bodies, outfits, colors, or signature props.",
            "STRICT RULE: ZERO visible text in the video. No letters, numbers, subtitles, captions, logos, watermarks, or UI elements anywhere in the frame.",
            "STRICTLY NO BGM; generate NO music or soundtrack unless BGM above explicitly asks for music. Only sounds listed in ASMR may exist.",
        ]

        return (
            f"SCENE {scene_id}\n"
            "VIDEO PROMPT:\n"
            f"{' '.join(part for part in video_parts if part).strip()}\n"
            "AUDIO / TTS:\n"
            f"{' '.join(part for part in audio_parts if part).strip()}\n"
            f"{' '.join(strict_rules)}"
        ).strip()

    def _storytelling_item_from_prompt(self, prompt_text: str, index: int) -> dict:
        prompt_obj = self._parse_storytelling_prompt_object(prompt_text)
        if not prompt_obj:
            return {
                "description": str(prompt_text or "").strip(),
                "narration": "",
                "source_type": "storytelling_image",
                "aspect_ratio": str(getattr(self._cfg, "video_aspect_ratio", "9:16") or "9:16"),
                "storytelling_index": int(index),
            }

        def compact_json(value, max_chars: int = 1800) -> str:
            if value in (None, "", [], {}):
                return ""
            try:
                text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            except Exception:
                text = str(value)
            if len(text) > max_chars:
                return text[:max_chars].rstrip() + "..."
            return text

        dialogue_lines: list[str] = []
        dialogue = prompt_obj.get("dialogue")
        if isinstance(dialogue, list):
            for line in dialogue:
                if isinstance(line, dict):
                    line_text = str(line.get("line") or line.get("text") or line.get("content") or line.get("dialogue") or "").strip()
                else:
                    line_text = str(line or "").strip()
                line_text = self._clean_storytelling_narration_line(line_text)
                if line_text:
                    dialogue_lines.append(line_text)

        summary = str(prompt_obj.get("summary") or "").strip()
        narration = " ".join(dialogue_lines).strip() or summary

        parts = [
            "Create one cinematic storytelling still image only; do not create a video.",
            "No visible text, subtitles, captions, watermark, logo, UI, or written letters in the frame.",
        ]
        visual_style = str(prompt_obj.get("visual_style") or "").strip()
        if visual_style:
            parts.append(f"Output style: {visual_style}.")
        if summary:
            parts.append(f"Story moment: {summary}.")

        character_lock = compact_json(prompt_obj.get("character_lock"))
        if character_lock:
            parts.append(f"Character consistency: {character_lock}.")
        background_lock = compact_json(prompt_obj.get("background_lock"))
        if background_lock:
            parts.append(f"Setting/background: {background_lock}.")
        camera = compact_json(prompt_obj.get("camera"), max_chars=700)
        if camera:
            parts.append(f"Camera/composition: {camera}.")
        foley = compact_json(prompt_obj.get("foley_and_ambience"), max_chars=700)
        if foley:
            parts.append(f"Mood and atmosphere: {foley}.")
        parts.append("Make the image expressive enough to support a narrated story scene with clear emotion and readable action.")

        return {
            "description": " ".join(part for part in parts if part).strip(),
            "narration": narration.strip(),
            "source_type": "storytelling_image",
            "aspect_ratio": str(getattr(self._cfg, "video_aspect_ratio", "9:16") or "9:16"),
            "storytelling_index": int(index),
        }

    def _clean_copy_video_prompt_part(self, value: str) -> str:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        text = re.sub(r"^(scene action:|action:)\s*", "", text, flags=re.IGNORECASE)
        return text.rstrip(" .,;:")

    def _copy_strength_instruction(self, copy_strength: int) -> str:
        strength = _clamp_copy_strength(copy_strength)
        if strength <= 60:
            return (
                "inspired adaptation only; keep the core idea, core video style, and emotional arc, "
                "but use original character, environment, action, prop, and shot details"
            )
        if strength <= 75:
            return (
                "medium adaptation; preserve the main story beats, pacing, and style while changing "
                "specific visual details enough to feel original"
            )
        if strength < 100:
            return (
                "close adaptation; preserve most scene beats, camera language, and style with light "
                "variation in wording and secondary details"
            )
        return "faithful recreation; preserve the source structure, scene order, actions, camera language, and style"

    def _build_copy_video_scene_prompt(
        self,
        scene: dict,
        identity_context_en: str,
        copy_strength: int = 100,
        user_edit_instruction: str = "",
    ) -> str:
        scene_id = self._clean_copy_video_prompt_part(scene.get("scene_id") or "scene_001").lower()
        copy_strength = _clamp_copy_strength(copy_strength)
        narrative_role = self._clean_copy_video_prompt_part(scene.get("narrative_role") or "")

        shot_type = self._clean_copy_video_prompt_part(scene.get("shot_type") or "medium shot")
        camera_angle = self._clean_copy_video_prompt_part(scene.get("camera_angle") or "eye-level")
        framing = self._clean_copy_video_prompt_part(scene.get("framing") or "vertical 9:16 framing")
        lens_feel = self._clean_copy_video_prompt_part(scene.get("lens_feel") or "cinematic 2D lens feel")

        style_block = self._clean_copy_video_prompt_part(
            scene.get("style_block_en")
            or "2D animation style, flat perspective with clean outlines, bold line art, and simplified forms"
        )
        consistency_block = self._clean_copy_video_prompt_part(
            scene.get("render_consistency_en")
            or "consistent cel shading or flat coloring, no depth simulation"
        )
        motion_style_block = self._clean_copy_video_prompt_part(
            scene.get("motion_style_en")
            or "smooth but intentionally stylized, frame-by-frame animation feel"
        )

        identity_block = self._clean_copy_video_prompt_part(identity_context_en)
        scene_action_en = self._clean_copy_video_prompt_part(
            scene.get("scene_action_en")
            or scene.get("visual_summary_en")
            or scene.get("video_prompt_en")
            or ""
        )
        environment_en = self._clean_copy_video_prompt_part(scene.get("environment_en") or "")
        mood_en = self._clean_copy_video_prompt_part(scene.get("mood_en") or "")
        motion_en = self._clean_copy_video_prompt_part(scene.get("motion_en") or "")
        custom_instruction = self._clean_copy_video_prompt_part(
            scene.get("custom_instruction_en")
            or scene.get("user_edit_instruction_en")
            or scene.get("adaptation_instruction_en")
            or user_edit_instruction
        )

        parts: list[str] = [
            f"{scene_id.upper()}. Shot {shot_type}, {camera_angle}, {framing}, {lens_feel}.",
            f"Copy direction ({copy_strength}%): {self._copy_strength_instruction(copy_strength)}.",
            f"Style: {style_block}.",
            f"Characters and objects are illustrated with {consistency_block}.",
            f"Movements are {motion_style_block}.",
        ]

        if narrative_role:
            parts.append(f"Narrative role: {narrative_role}.")
        if custom_instruction:
            parts.append(f"User edit instruction to apply consistently: {custom_instruction}.")
        if identity_block:
            parts.append(f"Character consistency lock: {identity_block}.")
        if scene_action_en:
            parts.append(f"Scene action: {scene_action_en}.")
        if environment_en:
            parts.append(f"Environment and background: {environment_en}.")
        if mood_en:
            parts.append(f"Mood and atmosphere: {mood_en}.")
        if motion_en:
            parts.append(f"Motion details: {motion_en}.")

        return " ".join(part for part in parts if part).strip()

    def enqueue_text_to_video(self, prompts: list[str]) -> dict | None:
        self._ensure_status_snapshot_loaded()
        clean_prompts = [str(p or "").strip() for p in (prompts or []) if str(p or "").strip()]
        if not clean_prompts:
            QMessageBox.warning(self, "Không có prompt", "Hãy nhập ít nhất một prompt.")
            return None

        rows: list[int] = []
        for prompt_text in clean_prompts:
            row = self.table.rowCount()
            self._add_row(row, prompt_text)
            self._set_row_mode_meta(row, self.MODE_TEXT_TO_VIDEO, payload={"prompt": prompt_text})
            rows.append(row)

        self._sync_stt_and_prompt_ids()
        self._snapshot_output_count_for_rows(rows)
        self._update_empty_state()
        self._mark_rows_pending(rows)
        return {"mode_key": self.MODE_TEXT_TO_VIDEO, "rows": rows, "label": "VEO3 - Text to Video"}

    def enqueue_copy_video_scenes(
        self,
        copy_data: dict,
        voice_actor_key: str,
        target_language: str,
        source_video_path: str,
        video_model: str = "VEO 3",
    ) -> dict | None:
        self._ensure_status_snapshot_loaded()
        if not isinstance(copy_data, dict):
            return None

        characters = copy_data.get("characters") if isinstance(copy_data.get("characters"), list) else []
        copy_strength = _clamp_copy_strength(copy_data.get("copy_strength_percent") or copy_data.get("copy_strength") or 100)
        user_edit_instruction = str(
            copy_data.get("user_edit_instruction_en")
            or copy_data.get("user_edit_instruction")
            or copy_data.get("custom_instruction_en")
            or copy_data.get("custom_instruction")
            or ""
        ).strip()
        identity_map: dict[str, str] = {}
        for item in characters:
            if not isinstance(item, dict):
                continue
            character_id = str(item.get("character_id") or "").strip()
            character_name = str(item.get("display_name") or item.get("name") or character_id).strip()
            identity_lock = str(item.get("identity_lock_en") or "").strip()
            if character_id and identity_lock:
                identity_map[character_id] = f"Character '{character_name}': {identity_lock}"

        rows: list[int] = []
        scenes = copy_data.get("scenes") if isinstance(copy_data.get("scenes"), list) else []
        for idx, scene in enumerate(scenes, start=1):
            if not isinstance(scene, dict):
                continue
            video_prompt_en = str(scene.get("video_prompt_en") or "").strip()
            dialogue_target = str(scene.get("dialogue_target") or scene.get("dialogue") or "").strip()
            dialogue_original = str(scene.get("dialogue_original") or dialogue_target).strip()
            character_ids = [str(x).strip() for x in (scene.get("character_ids") or []) if str(x).strip()]
            identity_lines = [identity_map.get(character_id, "") for character_id in character_ids if identity_map.get(character_id, "")]
            identity_context_en = "; ".join([value for value in identity_lines if value])
            prompt_text = self._build_copy_video_scene_prompt(
                scene,
                identity_context_en,
                copy_strength,
                user_edit_instruction,
            )
            if not prompt_text:
                continue

            row = self.table.rowCount()
            self._add_row(row, prompt_text)
            payload = {
                "prompt": prompt_text,
                "source_type": "copy_video",
                "scene_id": str(scene.get("scene_id") or f"scene_{idx:02d}"),
                "character_ids": character_ids,
                "dialogue_original": dialogue_original,
                "dialogue_target": dialogue_target,
                "video_prompt_en": video_prompt_en,
                "copy_strength_percent": copy_strength,
                "user_edit_instruction": user_edit_instruction,
                "narrative_role": str(scene.get("narrative_role") or "").strip(),
                "custom_instruction_en": str(
                    scene.get("custom_instruction_en")
                    or scene.get("user_edit_instruction_en")
                    or scene.get("adaptation_instruction_en")
                    or ""
                ).strip(),
                "identity_context_en": identity_context_en,
                "shot_type": str(scene.get("shot_type") or "medium shot").strip(),
                "camera_angle": str(scene.get("camera_angle") or "eye-level").strip(),
                "framing": str(scene.get("framing") or "vertical 9:16 framing").strip(),
                "lens_feel": str(scene.get("lens_feel") or "cinematic 2D lens feel").strip(),
                "scene_action_en": str(scene.get("scene_action_en") or scene.get("visual_summary_en") or video_prompt_en).strip(),
                "environment_en": str(scene.get("environment_en") or "").strip(),
                "mood_en": str(scene.get("mood_en") or "").strip(),
                "motion_en": str(scene.get("motion_en") or "").strip(),
                "style_block_en": str(
                    scene.get("style_block_en")
                    or "2D animation style, flat perspective with clean outlines, bold line art, and simplified forms"
                ).strip(),
                "render_consistency_en": str(
                    scene.get("render_consistency_en")
                    or "consistent cel shading or flat coloring, no depth simulation"
                ).strip(),
                "motion_style_en": str(
                    scene.get("motion_style_en")
                    or "smooth but intentionally stylized, frame-by-frame animation feel"
                ).strip(),
                "voice_actor_key": str(voice_actor_key or "None_NoVoice"),
                "voice_profile": get_voice_profile_text(voice_actor_key),
                "target_language": normalize_locale(target_language) or "en-US",
                "detected_source_language": str(copy_data.get("detected_source_language") or "auto"),
                "source_video_path": str(source_video_path or "").strip(),
            }
            self._set_row_mode_meta(row, self.MODE_COPY_VIDEO, payload=payload)
            rows.append(row)

        if not rows:
            QMessageBox.warning(self, "Không có cảnh", "Gemini không trả về cảnh hợp lệ để render.")
            self._update_empty_state()
            return None

        self._sync_stt_and_prompt_ids()
        self._snapshot_output_count_for_rows(rows)
        self._update_empty_state()
        self._mark_rows_pending(rows)
        
        mode_key = self.MODE_GROK_TEXT_TO_VIDEO if video_model == "GROK" else self.MODE_COPY_VIDEO
        label = "GROK - Sao chép video" if video_model == "GROK" else "VEO3 - Sao chép video"
        
        for r in rows:
            self._set_row_mode_meta(r, mode_key, payload=self._table_data.get(r, {}))
            
        return {"mode_key": mode_key, "rows": rows, "label": label}

    def enqueue_grok_text_to_video(self, prompts: list[str]) -> dict | None:
        self._ensure_status_snapshot_loaded()
        clean_prompts = [str(p or "").strip() for p in (prompts or []) if str(p or "").strip()]
        if not clean_prompts:
            QMessageBox.warning(self, "Không có prompt", "Hãy nhập ít nhất một prompt GROK.")
            return None

        rows: list[int] = []
        for prompt_text in clean_prompts:
            row = self.table.rowCount()
            self._add_row(row, prompt_text)
            self._set_row_mode_meta(row, self.MODE_GROK_TEXT_TO_VIDEO, payload={"prompt": prompt_text})
            rows.append(row)

        self._sync_stt_and_prompt_ids()
        self._set_output_count_for_rows(rows, 1)
        self._update_empty_state()
        self._mark_rows_pending(rows)
        return {"mode_key": self.MODE_GROK_TEXT_TO_VIDEO, "rows": rows, "label": "GROK Text to Video"}

    def enqueue_grok_image_to_video(self, items: list[dict]) -> dict | None:
        self._ensure_status_snapshot_loaded()

        rows: list[int] = []
        for raw in items or []:
            if not isinstance(raw, dict):
                continue

            prompt_text = str(raw.get("prompt") or raw.get("description") or "").strip()
            image_link = str(raw.get("image_link") or raw.get("image") or raw.get("start_image_link") or "").strip()
            if not image_link:
                continue

            row = self.table.rowCount()
            self._add_row(row, prompt_text)
            self._set_row_mode_meta(
                row,
                self.MODE_GROK_IMAGE_TO_VIDEO,
                payload={
                    "prompt": prompt_text,
                    "image_link": image_link,
                },
            )
            rows.append(row)

        if not rows:
            QMessageBox.warning(self, "Không có dữ liệu", "Không có dữ liệu GROK Image to Video hợp lệ.")
            self._update_empty_state()
            return None

        self._sync_stt_and_prompt_ids()
        self._set_output_count_for_rows(rows, 1)
        self._update_empty_state()
        self._mark_rows_pending(rows)
        return {"mode_key": self.MODE_GROK_IMAGE_TO_VIDEO, "rows": rows, "label": "GROK Image to Video"}

    def enqueue_image_to_video(self, items: list[dict], mode: str = "single") -> dict | None:
        self._ensure_status_snapshot_loaded()
        normalized_mode = "start_end" if str(mode or "").strip().lower() == "start_end" else "single"

        rows: list[int] = []
        for raw in items or []:
            if not isinstance(raw, dict):
                continue

            prompt_text = str(raw.get("prompt") or raw.get("description") or "").strip()
            row = self.table.rowCount()
            self._add_row(row, prompt_text)

            if normalized_mode == "start_end":
                start_image_link = str(raw.get("start_image_link") or raw.get("image_link") or raw.get("image") or "").strip()
                end_image_link = str(raw.get("end_image_link") or raw.get("end_image") or "").strip()
                self._set_row_mode_meta(
                    row,
                    self.MODE_IMAGE_TO_VIDEO_START_END,
                    payload={
                        "prompt": prompt_text,
                        "start_image_link": start_image_link,
                        "end_image_link": end_image_link,
                    },
                )
            else:
                image_link = str(raw.get("image_link") or raw.get("image") or raw.get("start_image_link") or "").strip()
                self._set_row_mode_meta(
                    row,
                    self.MODE_IMAGE_TO_VIDEO_SINGLE,
                    payload={
                        "prompt": prompt_text,
                        "image_link": image_link,
                    },
                )

            rows.append(row)

        if not rows:
            QMessageBox.warning(self, "Không có dữ liệu", "Không có dữ liệu Image to Video hợp lệ.")
            self._update_empty_state()
            return None

        self._sync_stt_and_prompt_ids()
        self._snapshot_output_count_for_rows(rows)
        self._update_empty_state()
        self._mark_rows_pending(rows)
        mode_key = self.MODE_IMAGE_TO_VIDEO_START_END if normalized_mode == "start_end" else self.MODE_IMAGE_TO_VIDEO_SINGLE
        mode_label = "VEO3 - Image to Video (Ảnh đầu-cuối)" if normalized_mode == "start_end" else "VEO3 - Image to Video"
        return {"mode_key": mode_key, "rows": rows, "label": mode_label}

    def enqueue_generate_image_from_prompts(self, items: list[dict]) -> dict | None:
        self._ensure_status_snapshot_loaded()
        rows: list[int] = []
        for raw in items or []:
            if not isinstance(raw, dict):
                continue
            prompt_text = str(raw.get("description") or raw.get("prompt") or "").strip()
            if not prompt_text:
                continue
            row = self.table.rowCount()
            self._add_row(row, prompt_text)
            payload = {"description": prompt_text}
            aspect_ratio = str(raw.get("aspect_ratio") or "").strip()
            if aspect_ratio:
                payload["aspect_ratio"] = aspect_ratio
            source_type = str(raw.get("source_type") or "").strip()
            if source_type:
                payload["source_type"] = source_type
            character_id = str(raw.get("character_id") or "").strip()
            if character_id:
                payload["character_id"] = character_id
            character_name = str(raw.get("character_name") or "").strip()
            if character_name:
                payload["character_name"] = character_name
            narration = str(raw.get("narration") or "").strip()
            if narration:
                payload["narration"] = narration
            storytelling_index = raw.get("storytelling_index")
            if storytelling_index is not None:
                try:
                    payload["storytelling_index"] = int(storytelling_index)
                except Exception:
                    payload["storytelling_index"] = str(storytelling_index)
            self._set_row_mode_meta(row, self.MODE_CREATE_IMAGE_PROMPT, payload=payload)
            rows.append(row)

        if not rows:
            QMessageBox.warning(self, "Không có dữ liệu", "Không có prompt hợp lệ để tạo ảnh.")
            self._update_empty_state()
            return None

        self._sync_stt_and_prompt_ids()
        if any(self._is_storytelling_row(int(r)) for r in rows):
            self._set_output_count_for_rows(rows, 1)
        else:
            self._snapshot_output_count_for_rows(rows)
        self._update_empty_state()
        self._mark_rows_pending(rows)
        return {"mode_key": self.MODE_CREATE_IMAGE_PROMPT, "rows": rows, "label": "VEO3 - Tạo ảnh từ prompt"}

    def enqueue_generate_image_from_references(self, prompts: list[str], characters: list[dict]) -> dict | None:
        self._ensure_status_snapshot_loaded()
        clean_prompts = [str(p or "").strip() for p in (prompts or []) if str(p or "").strip()]
        clean_characters: list[dict] = []
        for ch in characters or []:
            if not isinstance(ch, dict):
                continue
            name = str(ch.get("name") or "").strip()
            path = str(ch.get("path") or "").strip()
            if name and path:
                clean_characters.append({"name": name, "path": path})

        if not clean_prompts:
            QMessageBox.warning(self, "Thiếu prompt", "Không có prompt hợp lệ để chạy Tạo Ảnh Từ Ảnh Tham Chiếu.")
            return None
        if not clean_characters:
            QMessageBox.warning(self, "Thiếu ảnh tham chiếu", "Không có ảnh tham chiếu hợp lệ để chạy Tạo Ảnh Từ Ảnh Tham Chiếu.")
            return None

        rows: list[int] = []
        for prompt_text in clean_prompts:
            row = self.table.rowCount()
            self._add_row(row, prompt_text)
            self._set_row_mode_meta(
                row,
                self.MODE_CREATE_IMAGE_REFERENCE,
                payload={"prompt": prompt_text, "characters": list(clean_characters)},
            )
            rows.append(row)

        self._sync_stt_and_prompt_ids()
        self._snapshot_output_count_for_rows(rows)
        self._update_empty_state()
        self._mark_rows_pending(rows)
        return {"mode_key": self.MODE_CREATE_IMAGE_REFERENCE, "rows": rows, "label": "VEO3 - Tạo ảnh từ ảnh tham chiếu"}

    def enqueue_character_sync(self, prompts: list[str], characters: list[dict]) -> dict | None:
        self._ensure_status_snapshot_loaded()
        clean_prompts = [str(p or "").strip() for p in (prompts or []) if str(p or "").strip()]
        clean_characters: list[dict] = []
        for ch in characters or []:
            if not isinstance(ch, dict):
                continue
            name = str(ch.get("name") or "").strip()
            path = str(ch.get("path") or "").strip()
            if name and path:
                clean_characters.append({"name": name, "path": path})

        if not clean_prompts:
            QMessageBox.warning(self, "Thiếu prompt", "Không có prompt hợp lệ để chạy Đồng bộ nhân vật.")
            return None
        if not clean_characters:
            QMessageBox.warning(self, "Thiếu ảnh nhân vật", "Không có ảnh nhân vật hợp lệ để chạy Đồng bộ nhân vật.")
            return None

        rows: list[int] = []
        for prompt_text in clean_prompts:
            row = self.table.rowCount()
            self._add_row(row, prompt_text)
            self._set_row_mode_meta(
                row,
                self.MODE_CHARACTER_SYNC,
                payload={"prompt": prompt_text, "characters": list(clean_characters)},
            )
            rows.append(row)

        self._sync_stt_and_prompt_ids()
        self._snapshot_output_count_for_rows(rows)
        self._update_empty_state()
        self._mark_rows_pending(rows)
        return {"mode_key": self.MODE_CHARACTER_SYNC, "rows": rows, "label": "VEO3 - Đồng bộ nhân vật"}

    def enqueue_grok_character_sync(self, prompts: list[str], characters: list[dict]) -> dict | None:
        self._ensure_status_snapshot_loaded()
        clean_prompts = [str(p or "").strip() for p in (prompts or []) if str(p or "").strip()]
        clean_characters: list[dict] = []
        for ch in characters or []:
            if not isinstance(ch, dict):
                continue
            name = str(ch.get("name") or "").strip()
            path = str(ch.get("path") or "").strip()
            if name and path:
                clean_characters.append({"name": name, "path": path})

        if not clean_prompts:
            QMessageBox.warning(self, "Thiếu prompt", "Không có prompt hợp lệ để chạy GROK Đồng bộ nhân vật.")
            return None
        if not clean_characters:
            QMessageBox.warning(self, "Thiếu ảnh nhân vật", "Không có ảnh nhân vật hợp lệ để chạy GROK Đồng bộ nhân vật.")
            return None

        rows: list[int] = []
        for prompt_text in clean_prompts:
            found_paths = []
            lowered = prompt_text.lower()
            for ch in clean_characters:
                name = ch["name"]
                escaped = re.escape(name.lower())
                pattern = r"(?<![\w])" + escaped + r"(?![\w])"
                m = re.search(pattern, lowered, flags=re.IGNORECASE)
                if m or name.lower() in lowered:
                    if ch["path"] not in found_paths:
                        found_paths.append(ch["path"])
            
            image_link = "|".join(found_paths)
            if not image_link:
                image_link = clean_characters[0]["path"]

            row = self.table.rowCount()
            self._add_row(row, prompt_text)
            self._set_row_mode_meta(
                row,
                self.MODE_GROK_IMAGE_TO_VIDEO,
                payload={"prompt": prompt_text, "image_link": image_link},
            )
            rows.append(row)

        self._sync_stt_and_prompt_ids()
        self._snapshot_output_count_for_rows(rows)
        self._update_empty_state()
        self._mark_rows_pending(rows)
        return {"mode_key": self.MODE_GROK_IMAGE_TO_VIDEO, "rows": rows, "label": "GROK - Đồng bộ nhân vật"}

    def start_queued_job(self, mode_key: str, rows: list[int]) -> bool:
        self._global_stop_requested = False
        clean_rows = [int(r) for r in (rows or [])]
        if not clean_rows:
            return False
        self._retry_mode_queue = []
        started = self._start_mode_group(str(mode_key or ""), clean_rows)
        if started:
            self._active_queue_rows = {int(r) for r in clean_rows}
            self._awaiting_completion_confirmation = False
            self._completion_poll_attempts = 0
            self._completion_poll_scheduled = False
        return bool(started)

    def start_text_to_video(self, prompts: list[str]) -> None:
        if self.isRunning():
            QMessageBox.information(self, "Đang chạy", "Workflow đang chạy, hãy dừng trước khi chạy mới.")
            return
        payload = self.enqueue_text_to_video(prompts)
        if not payload:
            return
        self.start_queued_job(str(payload.get("mode_key") or ""), list(payload.get("rows") or []))

    def start_image_to_video(self, items: list[dict], mode: str = "single") -> None:
        if self.isRunning():
            QMessageBox.information(self, "Đang chạy", "Workflow đang chạy, hãy dừng trước khi chạy mới.")
            return
        payload = self.enqueue_image_to_video(items, mode=mode)
        if not payload:
            return
        self.start_queued_job(str(payload.get("mode_key") or ""), list(payload.get("rows") or []))

    def start_generate_image_from_prompts(self, items: list[dict]) -> None:
        if self.isRunning():
            QMessageBox.information(self, "Đang chạy", "Workflow đang chạy, hãy dừng trước khi chạy mới.")
            return
        payload = self.enqueue_generate_image_from_prompts(items)
        if not payload:
            return
        self.start_queued_job(str(payload.get("mode_key") or ""), list(payload.get("rows") or []))

    def start_generate_image_from_references(self, prompts: list[str], characters: list[dict]) -> None:
        if self.isRunning():
            QMessageBox.information(self, "Đang chạy", "Workflow đang chạy, hãy dừng trước khi chạy mới.")
            return
        payload = self.enqueue_generate_image_from_references(prompts, characters)
        if not payload:
            return
        self.start_queued_job(str(payload.get("mode_key") or ""), list(payload.get("rows") or []))

    def start_character_sync(self, prompts: list[str], characters: list[dict]) -> None:
        if self.isRunning():
            QMessageBox.information(self, "Đang chạy", "Workflow đang chạy, hãy dừng trước khi chạy mới.")
            return
        payload = self.enqueue_character_sync(prompts, characters)
        if not payload:
            return
        self.start_queued_job(str(payload.get("mode_key") or ""), list(payload.get("rows") or []))

    def _add_row(self, row: int, prompt: str) -> None:
        self.table.insertRow(row)
        try:
            self.table.setRowHeight(int(row), 120)
        except Exception:
            pass

        # Column 0: keep an item for selection + store checked state in UserRole,
        # and place a centered toolbutton widget for the icon.
        chk_item = QTableWidgetItem("")
        chk_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        chk_item.setText("")
        chk_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        chk_item.setData(Qt.ItemDataRole.UserRole, False)
        self.table.setItem(row, self.COL_CHECK, chk_item)

        w = QWidget()
        w.setContentsMargins(0, 0, 0, 0)
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        btn = QToolButton()
        btn.setAutoRaise(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedSize(22, 22)
        btn.setIconSize(btn.size())
        self._apply_checkbox_button_state(btn, False)
        btn.clicked.connect(lambda _=False, cell_widget=w: self._toggle_row_checked_by_widget(cell_widget))
        lay.addStretch(1)
        lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignCenter)
        lay.addStretch(1)
        setattr(w, "_cb_btn", btn)
        self.table.setCellWidget(row, self.COL_CHECK, w)

        stt = QTableWidgetItem(f"{row+1:03d}")
        stt.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, self.COL_STT, stt)

        st = QTableWidgetItem("Sẵn sàng")
        st.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        st.setData(Qt.ItemDataRole.UserRole, "READY")
        self.table.setItem(row, self.COL_STATUS, st)

        mode_item = QTableWidgetItem(self._mode_label(self.MODE_TEXT_TO_VIDEO))
        mode_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        mode_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, self.COL_MODE, mode_item)

        pr = QTableWidgetItem(str(prompt or ""))
        pr.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        pr.setData(Qt.ItemDataRole.UserRole, str(int(row) + 1))
        pr.setForeground(QBrush(QColor("transparent")))
        self.table.setItem(row, self.COL_PROMPT, pr)
        self._set_row_mode_meta(
            row,
            self.MODE_TEXT_TO_VIDEO,
            payload={"prompt": str(prompt or "").strip()},
        )
        self._setup_prompt_cell(row)

        # Video column placeholder (blank until video thumbnail is available).
        vid_item = QTableWidgetItem("")
        vid_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        try:
            vid_item.setData(Qt.ItemDataRole.UserRole, "")
            vid_item.setData(Qt.ItemDataRole.UserRole + 1, {})
            vid_item.setData(Qt.ItemDataRole.UserRole + 2, 1)
            vid_item.setData(Qt.ItemDataRole.UserRole + 3, self._expected_output_count())
            vid_item.setData(Qt.ItemDataRole.UserRole + 4, {})
        except Exception:
            pass
        self.table.setItem(row, self.COL_VIDEO, vid_item)
        self._setup_video_cell(row)

        self._sync_select_all_header()
        self._update_empty_state()
        if not self._loading_status_snapshot:
            self._save_status_snapshot()
            self._update_status_summary()

    def _find_row_by_cell_widget(self, column: int, widget: QWidget | None) -> int:
        if widget is None:
            return -1
        for r in range(self.table.rowCount()):
            if self.table.cellWidget(r, int(column)) is widget:
                return r
        return -1

    def _toggle_row_checked_by_widget(self, widget: QWidget | None) -> None:
        row = self._find_row_by_cell_widget(self.COL_CHECK, widget)
        if row < 0:
            return
        self._toggle_row_checked(int(row))

    def _edit_prompt_by_widget(self, widget: QWidget | None) -> None:
        row = self._find_row_by_cell_widget(self.COL_PROMPT, widget)
        if row < 0:
            return
        self._open_prompt_editor(int(row))

    def _setup_prompt_cell(self, row: int) -> None:
        wrap = QWidget()
        wrap.setContentsMargins(0, 0, 0, 0)
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(0)

        btn = QPushButton("Sửa")
        btn.setObjectName("TopAction")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(22)
        btn.setStyleSheet("padding: 0 10px; font-weight:700;")
        btn.clicked.connect(lambda _=False, cell_widget=wrap: self._edit_prompt_by_widget(cell_widget))
        top_row.addWidget(btn, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        top_row.addStretch(1)

        lbl = QLabel("")
        lbl.setObjectName("PromptCellLabel")
        lbl.setStyleSheet("color:#1f2d48;")
        lbl.setTextFormat(Qt.TextFormat.PlainText)
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        lay.addLayout(top_row)
        lay.addWidget(lbl, 1)
        setattr(wrap, "_prompt_label", lbl)
        setattr(wrap, "_prompt_btn", btn)
        self.table.setCellWidget(int(row), self.COL_PROMPT, wrap)
        self._refresh_prompt_cell(int(row))

    def _refresh_prompt_cell(self, row: int) -> None:
        cell = self.table.cellWidget(int(row), self.COL_PROMPT)
        if cell is None:
            return
        lbl = getattr(cell, "_prompt_label", None)
        if not isinstance(lbl, QLabel):
            return
        btn = getattr(cell, "_prompt_btn", None)
        item = self.table.item(int(row), self.COL_PROMPT)
        if item is not None:
            try:
                item.setForeground(QBrush(QColor("transparent")))
            except Exception:
                pass
        txt = str((item.text() if item is not None else "") or "").strip()
        lbl.setText(txt)
        lbl.setToolTip(txt)

    def _open_prompt_editor(self, row: int) -> None:
        item = self.table.item(int(row), self.COL_PROMPT)
        if item is None:
            return
        current_text = str(item.text() or "")

        dlg = QDialog(self)
        dlg.setWindowTitle("Sửa Prompt")
        dlg.setModal(True)
        dlg.resize(760, 420)
        dlg.setStyleSheet(
            "QDialog{background:#ffffff;}"
            "QLabel{color:#1f2d48;font-weight:700;}"
            "QTextEdit{background:#ffffff;border:1px solid #c8d7f2;border-radius:8px;padding:8px;color:#1f2d48;}"
            "QPushButton{min-height:32px;border-radius:8px;padding:0 14px;font-weight:700;}"
            "QPushButton#okBtn{background:#2f63d9;color:white;}"
            "QPushButton#cancelBtn{background:#eaf2ff;color:#1f2d48;}"
        )

        root = QVBoxLayout(dlg)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)
        root.addWidget(QLabel("Prompt hiện tại / chỉnh sửa:"))

        editor = QTextEdit()
        editor.setPlainText(current_text)
        root.addWidget(editor, 1)

        buttons = QDialogButtonBox()
        ok_btn = buttons.addButton("Xác nhận", QDialogButtonBox.ButtonRole.AcceptRole)
        ok_btn.setObjectName("okBtn")
        cancel_btn = buttons.addButton("Hủy", QDialogButtonBox.ButtonRole.RejectRole)
        cancel_btn.setObjectName("cancelBtn")
        ok_btn.clicked.connect(dlg.accept)
        cancel_btn.clicked.connect(dlg.reject)
        root.addWidget(buttons)

        if dlg.exec() != int(QDialog.DialogCode.Accepted):
            return

        new_text = str(editor.toPlainText() or "").strip()
        if not new_text or new_text == current_text.strip():
            return

        item.setText(new_text)
        payload = self._row_mode_payload(int(row))
        if isinstance(payload, dict):
            if "description" in payload:
                payload["description"] = new_text
            else:
                payload["prompt"] = new_text
            self._set_row_mode_meta(int(row), self._row_mode_key(int(row)), payload=payload)
        self._refresh_prompt_cell(int(row))
        self._save_status_snapshot()

    def _on_table_item_changed(self, item: QTableWidgetItem) -> None:
        if item is None:
            return
        if int(item.column()) != self.COL_PROMPT:
            return
        row = int(item.row())
        self._refresh_prompt_cell(row)
        if not self._loading_status_snapshot:
            self._save_status_snapshot()

    def _on_cell_clicked(self, row: int, col: int) -> None:
        # Column 0 uses a toolbutton; ignore clicks on the cell background.
        if int(col) == self.COL_CHECK:
            return
        if int(col) != self.COL_VIDEO:
            return
        it = self.table.item(int(row), self.COL_VIDEO)
        try:
            path = str(it.data(Qt.ItemDataRole.UserRole) or "").strip() if it is not None else ""
        except Exception:
            path = ""
        if not path or not os.path.isfile(path):
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _setup_video_cell(self, row: int) -> None:
        vw = QWidget()
        vw.setContentsMargins(0, 0, 0, 0)
        vlay = QVBoxLayout(vw)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)

        preview = QWidget(vw)
        preview.setContentsMargins(0, 0, 0, 0)
        pv_lay = QVBoxLayout(preview)
        pv_lay.setContentsMargins(0, 0, 0, 0)
        pv_lay.setSpacing(0)

        buttons = []
        expected_outputs = self._expected_output_count()
        for idx in range(1, 5):
            b = QPushButton(str(idx), preview)
            b.setFixedSize(20, 20)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet("border-radius:10px; font-size:10px; padding:0px;")
            should_show = expected_outputs >= 2 and idx <= expected_outputs
            b.setVisible(should_show)
            b.setEnabled(False)
            if should_show:
                b.setStyleSheet("border-radius:10px; font-size:10px; padding:0px; background:#f3f4f6; color:#9ca3af;")
            b.clicked.connect(lambda _=False, cell_widget=vw, n=idx: self._select_video_output_by_widget(cell_widget, n))
            buttons.append(b)

        vlabel = QLabel("", preview)
        vlabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vlabel.setStyleSheet("color:#1f2d48; font-weight:700;")
        vlabel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        pv_lay.addWidget(vlabel, 1)
        vlay.addWidget(preview, 1)
        preview.installEventFilter(self)
        setattr(vw, "_vid_label", vlabel)
        setattr(vw, "_vid_buttons", buttons)
        setattr(vw, "_vid_preview", preview)
        self.table.setCellWidget(row, self.COL_VIDEO, vw)
        self._reposition_video_badges(preview)

    def _select_video_output_by_widget(self, widget: QWidget | None, output_index: int) -> None:
        row = self._find_row_by_cell_widget(self.COL_VIDEO, widget)
        if row < 0:
            return
        self._select_video_output(int(row), int(output_index))

    def eventFilter(self, watched, event):
        try:
            if event.type() == event.Type.Resize and isinstance(watched, QWidget):
                self._reposition_video_badges(watched)
        except Exception:
            pass
        return super().eventFilter(watched, event)

    def _reposition_video_badges(self, preview_widget: QWidget) -> None:
        row = -1
        for r in range(self.table.rowCount()):
            cell = self.table.cellWidget(r, self.COL_VIDEO)
            if cell is None:
                continue
            pv = getattr(cell, "_vid_preview", None)
            if pv is preview_widget:
                row = r
                break
        if row < 0:
            return
        cell = self.table.cellWidget(row, self.COL_VIDEO)
        if cell is None:
            return
        buttons = getattr(cell, "_vid_buttons", [])
        visible_btns = [b for b in buttons if isinstance(b, QPushButton) and b.isVisible()]
        if not visible_btns:
            return
        right = int(preview_widget.width()) - 4
        top = 4
        for b in reversed(visible_btns):
            b.move(right - b.width(), top)
            try:
                b.raise_()
            except Exception:
                pass
            right -= (b.width() + 4)

    def _select_video_output(self, row: int, output_index: int) -> None:
        it = self.table.item(int(row), self.COL_VIDEO)
        if it is None:
            return
        try:
            video_map = dict(it.data(Qt.ItemDataRole.UserRole + 1) or {})
        except Exception:
            video_map = {}
        try:
            preview_map = dict(it.data(Qt.ItemDataRole.UserRole + 4) or {})
        except Exception:
            preview_map = {}
        path = str(video_map.get(int(output_index), "") or "")
        if not path:
            return
        it.setData(Qt.ItemDataRole.UserRole + 2, int(output_index))
        it.setData(Qt.ItemDataRole.UserRole, path)
        preview_path = str(preview_map.get(int(output_index), "") or path)
        self._render_media_preview(row, preview_path)
        self._refresh_video_badges(row)
        try:
            if os.path.isfile(path):
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        except Exception:
            pass

    def _is_image_file(self, file_path: str) -> bool:
        ext = str(Path(str(file_path or "")).suffix or "").lower()
        return ext in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}

    def _refresh_video_badges(self, row: int) -> None:
        it = self.table.item(int(row), self.COL_VIDEO)
        if it is None:
            return
        try:
            video_map = dict(it.data(Qt.ItemDataRole.UserRole + 1) or {})
        except Exception:
            video_map = {}
        try:
            selected_idx = int(it.data(Qt.ItemDataRole.UserRole + 2) or 1)
        except Exception:
            selected_idx = 1

        cell = self.table.cellWidget(int(row), self.COL_VIDEO)
        if cell is None:
            return
        buttons = getattr(cell, "_vid_buttons", [])
        expected_outputs = self._row_output_count(int(row))
        for i, btn in enumerate(buttons, start=1):
            should_show = expected_outputs >= 2 and i <= expected_outputs
            has_video = i in video_map
            btn.setVisible(should_show)
            btn.setEnabled(has_video)
            if should_show and has_video and i == selected_idx:
                btn.setStyleSheet("border-radius:10px; font-size:10px; padding:0px; background:#2563eb; color:#fff;")
            elif should_show and has_video:
                btn.setStyleSheet("border-radius:10px; font-size:10px; padding:0px; background:#eaf2ff; color:#1f2d48;")
            elif should_show:
                btn.setStyleSheet("border-radius:10px; font-size:10px; padding:0px; background:#f3f4f6; color:#9ca3af;")
            try:
                btn.raise_()
            except Exception:
                pass
        preview = getattr(cell, "_vid_preview", None)
        if isinstance(preview, QWidget):
            self._reposition_video_badges(preview)

    def _expected_output_count(self) -> int:
        try:
            val = int(getattr(self._cfg, "output_count", 1) or 1)
        except Exception:
            val = 1
        if val < 1:
            val = 1
        if val > 4:
            val = 4
        return val

    def _row_output_count(self, row: int) -> int:
        it = self.table.item(int(row), self.COL_VIDEO)
        if it is not None:
            try:
                v = int(it.data(Qt.ItemDataRole.UserRole + 3) or 0)
                if 1 <= v <= 4:
                    return v
            except Exception:
                pass
        return self._expected_output_count()

    def _snapshot_output_count_for_rows(self, rows: list[int]) -> None:
        snap = self._expected_output_count()
        for r in rows:
            it = self.table.item(int(r), self.COL_VIDEO)
            if it is None:
                continue
            try:
                it.setData(Qt.ItemDataRole.UserRole + 3, int(snap))
            except Exception:
                pass
            self._refresh_video_badges(int(r))

    def _set_output_count_for_rows(self, rows: list[int], output_count: int) -> None:
        try:
            snap = int(output_count)
        except Exception:
            snap = 1
        if snap < 1:
            snap = 1
        if snap > 4:
            snap = 4
        for r in rows:
            it = self.table.item(int(r), self.COL_VIDEO)
            if it is None:
                continue
            try:
                it.setData(Qt.ItemDataRole.UserRole + 3, int(snap))
            except Exception:
                pass
            self._refresh_video_badges(int(r))

    def _render_video_preview(self, row: int, video_path: str) -> None:
        cell = self.table.cellWidget(int(row), self.COL_VIDEO)
        if cell is None:
            return
        label = getattr(cell, "_vid_label", None)
        if not isinstance(label, QLabel):
            return
        if not video_path or not os.path.isfile(video_path):
            label.setText("")
            label.setPixmap(QPixmap())
            return

        thumb_path = self._ensure_video_thumbnail(video_path)
        if thumb_path and os.path.isfile(thumb_path):
            self._render_image_preview(row, thumb_path)
            return

        label.setPixmap(QPixmap())
        label.setText("")

    def _on_thumbnail_ready(self, src_video_path: str, thumb_path: str) -> None:
        src = str(src_video_path or "").strip()
        thumb = str(thumb_path or "").strip()
        if not src or not thumb or not os.path.isfile(thumb):
            return
        try:
            src_norm = os.path.normcase(os.path.normpath(src))
        except Exception:
            src_norm = src

        for row in range(self.table.rowCount()):
            item = self.table.item(int(row), self.COL_VIDEO)
            if item is None:
                continue
            selected_path = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
            if not selected_path:
                continue
            try:
                selected_norm = os.path.normcase(os.path.normpath(selected_path))
            except Exception:
                selected_norm = selected_path
            if selected_norm != src_norm:
                continue

            try:
                selected_idx = int(item.data(Qt.ItemDataRole.UserRole + 2) or 1)
            except Exception:
                selected_idx = 1
            try:
                preview_map = dict(item.data(Qt.ItemDataRole.UserRole + 4) or {})
            except Exception:
                preview_map = {}
            preview_map[int(selected_idx)] = thumb
            item.setData(Qt.ItemDataRole.UserRole + 4, preview_map)
            self._render_image_preview(int(row), thumb)

    def _ensure_video_thumbnail(self, video_path: str) -> str:
        src = str(video_path or "").strip()
        if not src or not os.path.isfile(src):
            return ""

        src_path = Path(src)
        thumb_path = src_path.with_suffix(src_path.suffix + ".thumb.jpg")

        try:
            src_parts = [str(p).lower() for p in src_path.parts]
            if "grok_video" in src_parts:
                base_dir = src_path.parent.parent if src_path.parent.parent else src_path.parent
                grok_thumb_dir = base_dir / "grok_thumnail"
                grok_thumb_dir.mkdir(parents=True, exist_ok=True)
                thumb_path = grok_thumb_dir / f"{src_path.stem}.thumb.jpg"
        except Exception:
            pass

        try:
            if thumb_path.is_file() and thumb_path.stat().st_mtime >= src_path.stat().st_mtime:
                return str(thumb_path)
        except Exception:
            pass

        src_key = str(src_path).lower()
        try:
            src_mtime = float(src_path.stat().st_mtime)
        except Exception:
            src_mtime = 0.0

        last_attempt = float(self._thumb_attempted_mtime.get(src_key, 0.0) or 0.0)
        if last_attempt >= src_mtime:
            return ""

        if src_key not in self._thumb_jobs_inflight:
            self._thumb_jobs_inflight.add(src_key)

            def _build_thumb_async() -> None:
                try:
                    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
                    cmd = [
                        str(ffmpeg_exe),
                        "-y",
                        "-ss",
                        "00:00:00.500",
                        "-i",
                        str(src_path),
                        "-frames:v",
                        "1",
                        "-q:v",
                        "3",
                        str(thumb_path),
                    ]
                    subprocess.run(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                        timeout=12,
                        **_win_hidden_kwargs(),
                    )
                except Exception:
                    pass
                finally:
                    self._thumb_attempted_mtime[src_key] = src_mtime
                    self._thumb_jobs_inflight.discard(src_key)
                    try:
                        if thumb_path.is_file():
                            self.thumbnailReady.emit(str(src_path), str(thumb_path))
                    except Exception:
                        pass

            try:
                threading.Thread(target=_build_thumb_async, daemon=True).start()
            except Exception:
                self._thumb_attempted_mtime[src_key] = src_mtime
                self._thumb_jobs_inflight.discard(src_key)
        return ""

    def _render_image_preview(self, row: int, image_path: str) -> None:
        cell = self.table.cellWidget(int(row), self.COL_VIDEO)
        if cell is None:
            return
        label = getattr(cell, "_vid_label", None)
        if not isinstance(label, QLabel):
            return
        if not image_path or not os.path.isfile(image_path):
            label.setText("")
            label.setPixmap(QPixmap())
            return
        pix = QPixmap(image_path)
        if pix.isNull():
            label.setText("")
            label.setPixmap(QPixmap())
            return
        target = label.size()
        if target.width() < 2 or target.height() < 2:
            target = label.parentWidget().size() if label.parentWidget() else target
        label.setPixmap(
            pix.scaled(
                target,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        label.setText("")

    def _render_media_preview(self, row: int, media_path: str) -> None:
        if self._is_image_file(media_path):
            self._render_image_preview(row, media_path)
            return
        self._render_video_preview(row, media_path)

    def _set_video_progress_text(self, row: int, progress: int) -> None:
        pct = max(0, min(100, int(progress or 0)))
        if self._row_media_map(int(row)):
            return

        it = self.table.item(int(row), self.COL_VIDEO)
        if it is None:
            it = QTableWidgetItem("")
            it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(int(row), self.COL_VIDEO, it)
        it.setText(f"{pct}%")

        cell = self.table.cellWidget(int(row), self.COL_VIDEO)
        if cell is None:
            return
        label = getattr(cell, "_vid_label", None)
        if not isinstance(label, QLabel):
            return
        label.setPixmap(QPixmap())
        label.setText(f"{pct}%")

    def _selected_rows(self) -> list[int]:
        rows: list[int] = []
        for r in range(self.table.rowCount()):
            if self._row_checked(r):
                rows.append(r)
        return rows

    def delete_selected_rows(self) -> None:
        picked = sorted(set(self._selected_rows()))
        if not picked:
            QMessageBox.warning(self, "Chưa chọn", "Hãy tích chọn các dòng cần xóa kết quả.")
            return

        if QMessageBox.question(
            self,
            "Xác nhận",
            f"Bạn có chắc muốn xóa {len(picked)} kết quả đã chọn?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return

        for r in reversed(picked):
            self.table.removeRow(r)

        self._sync_stt_and_prompt_ids()

        self._sync_select_all_header()
        self._update_empty_state()
        self._save_status_snapshot()
        self._update_status_summary()

    def _collect_prompts_from_rows(self, rows: list[int]) -> list[str]:
        prompts: list[str] = []
        for r in rows:
            it = self.table.item(int(r), self.COL_PROMPT)
            txt = (it.text() if it is not None else "") or ""
            txt = str(txt).strip()
            if txt:
                prompts.append(txt)
        return prompts

    def _next_prompt_id(self) -> str:
        max_id = 0
        for r in range(self.table.rowCount()):
            it = self.table.item(r, self.COL_PROMPT)
            if it is None:
                continue
            try:
                val = str(it.data(Qt.ItemDataRole.UserRole) or "").strip()
                max_id = max(max_id, int(val))
            except Exception:
                continue
        return str(max_id + 1)

    def _mode_label(self, mode_key: str) -> str:
        key = str(mode_key or "").strip()
        labels = {
            self.MODE_COPY_VIDEO: "VEO3 - Sao chép video",
            self.MODE_TEXT_TO_VIDEO: "VEO3 - Tạo video từ văn bản",
            self.MODE_GROK_TEXT_TO_VIDEO: "GROK - Tạo video từ văn bản",
            self.MODE_GROK_IMAGE_TO_VIDEO: "GROK - Tạo video từ Ảnh",
            self.MODE_IMAGE_TO_VIDEO_SINGLE: "VEO3 - Tạo video từ Ảnh",
            self.MODE_IMAGE_TO_VIDEO_START_END: "VEO3 - Tạo video từ Ảnh (đầu-cuối)",
            self.MODE_CHARACTER_SYNC: "VEO3 - Video đồng nhất nhân vật",
            self.MODE_CREATE_IMAGE_PROMPT: "VEO3 - Tạo ảnh từ prompt",
            self.MODE_CREATE_IMAGE_REFERENCE: "VEO3 - Tạo ảnh từ ảnh tham chiếu",
        }
        return labels.get(key, "VEO3 - Tạo video từ văn bản")

    def _set_row_mode_meta(self, row: int, mode_key: str, payload: dict | None = None) -> None:
        prompt_item = self.table.item(int(row), self.COL_PROMPT)
        if prompt_item is None:
            return
        key = str(mode_key or self.MODE_TEXT_TO_VIDEO).strip() or self.MODE_TEXT_TO_VIDEO
        prompt_item.setData(Qt.ItemDataRole.UserRole + 1, key)
        mode_label = self._mode_label(key)
        prompt_item.setData(Qt.ItemDataRole.UserRole + 2, mode_label)
        prompt_item.setData(Qt.ItemDataRole.UserRole + 3, dict(payload or {}))
        mode_item = self.table.item(int(row), self.COL_MODE)
        if mode_item is None:
            mode_item = QTableWidgetItem(mode_label)
            mode_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            mode_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(int(row), self.COL_MODE, mode_item)
        else:
            mode_item.setText(mode_label)

    def _row_mode_key(self, row: int) -> str:
        prompt_item = self.table.item(int(row), self.COL_PROMPT)
        if prompt_item is None:
            return self.MODE_TEXT_TO_VIDEO
        try:
            key = str(prompt_item.data(Qt.ItemDataRole.UserRole + 1) or "").strip()
        except Exception:
            key = ""
        return key or self.MODE_TEXT_TO_VIDEO

    def _row_mode_label(self, row: int) -> str:
        key = self._row_mode_key(int(row))
        prompt_item = self.table.item(int(row), self.COL_PROMPT)
        if prompt_item is None:
            return self._mode_label(key)
        try:
            label = str(prompt_item.data(Qt.ItemDataRole.UserRole + 2) or "").strip()
        except Exception:
            label = ""
        return label or self._mode_label(key)

    def _row_mode_payload(self, row: int) -> dict:
        prompt_item = self.table.item(int(row), self.COL_PROMPT)
        if prompt_item is None:
            return {}
        try:
            raw = prompt_item.data(Qt.ItemDataRole.UserRole + 3)
        except Exception:
            raw = None
        return dict(raw) if isinstance(raw, dict) else {}

    def _sync_stt_and_prompt_ids(self) -> None:
        for r in range(self.table.rowCount()):
            stt_item = self.table.item(r, self.COL_STT)
            if stt_item is not None:
                stt_item.setText(f"{r+1:03d}")
            prompt_item = self.table.item(r, self.COL_PROMPT)
            if prompt_item is not None:
                prompt_item.setData(Qt.ItemDataRole.UserRole, str(r + 1))

    def _collect_existing_prompt_ids(self) -> set[str]:
        ids: set[str] = set()
        for r in range(self.table.rowCount()):
            prompt_id = self._prompt_id_of_row(r)
            if prompt_id:
                ids.add(prompt_id)
        return ids

    def _resolve_unique_prompt_id(self, preferred_id: str, used_ids: set[str]) -> str:
        candidate = str(preferred_id or "").strip()
        if candidate and candidate not in used_ids:
            used_ids.add(candidate)
            return candidate

        next_id = 1
        while str(next_id) in used_ids:
            next_id += 1
        resolved = str(next_id)
        used_ids.add(resolved)
        return resolved

    def _status_code(self, row: int) -> str:
        it = self.table.item(int(row), self.COL_STATUS)
        if it is None:
            return "READY"
        try:
            return str(it.data(Qt.ItemDataRole.UserRole) or "READY")
        except Exception:
            return "READY"

    def _set_status_code(self, row: int, code: str) -> None:
        item = self.table.item(int(row), self.COL_STATUS)
        if item is None:
            item = QTableWidgetItem("")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(int(row), self.COL_STATUS, item)
        item.setData(Qt.ItemDataRole.UserRole, str(code or "READY"))

    def _row_auto_retry_count(self, row: int) -> int:
        item = self.table.item(int(row), self.COL_STATUS)
        if item is None:
            return 0
        try:
            return max(0, int(item.data(Qt.ItemDataRole.UserRole + 10) or 0))
        except Exception:
            return 0

    def _set_row_auto_retry_count(self, row: int, count: int) -> None:
        item = self.table.item(int(row), self.COL_STATUS)
        if item is None:
            item = QTableWidgetItem("")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(int(row), self.COL_STATUS, item)
        try:
            item.setData(Qt.ItemDataRole.UserRole + 10, max(0, int(count or 0)))
        except Exception:
            pass

    def _is_auto_retryable_error_text(self, text: str) -> bool:
        raw = str(text or "")
        if not raw:
            return False
        return bool(re.search(r"(?<!\d)(403|500|13)(?!\d)", raw))

    def _row_failed_error_text(self, row: int) -> str:
        item = self.table.item(int(row), self.COL_STATUS)
        if item is None:
            return ""
        parts: list[str] = []
        try:
            parts.append(str(item.data(Qt.ItemDataRole.UserRole + 6) or "").strip())
        except Exception:
            pass
        try:
            parts.append(str(item.data(Qt.ItemDataRole.UserRole + 7) or "").strip())
        except Exception:
            pass
        parts.append(str(item.text() or "").strip())
        return " | ".join([p for p in parts if p])

    def get_auto_retry_rows_for_worker(self, mode_key: str, rows: list[int], retry_round: int = 0) -> list[int]:
        if int(retry_round or 0) >= self.AUTO_RETRY_MAX_PER_ROW:
            return []

        retry_rows: list[int] = []
        for r in [int(x) for x in (rows or [])]:
            if r < 0 or r >= self.table.rowCount():
                continue
            if self._status_code(r) != "FAILED":
                continue
            if self._row_auto_retry_count(r) >= self.AUTO_RETRY_MAX_PER_ROW:
                continue
            failed_text = self._row_failed_error_text(r)
            if not self._is_auto_retryable_error_text(failed_text):
                continue
            self._set_row_auto_retry_count(r, self._row_auto_retry_count(r) + 1)
            self._set_status_code(r, "PENDING")
            retry_rows.append(r)

        if retry_rows:
            self._refresh_pending_positions()
            self._append_run_log(
                f"🔁 Worker yêu cầu retry mã lỗi 403/13/500: {self._mode_label(str(mode_key or ''))} "
                f"({len(retry_rows)} dòng)"
            )
        return retry_rows

    def _status_text(self, code: str, queue_position: int = 0) -> str:
        c = str(code or "").upper()
        if c == "TOKEN":
            return "Đang tạo"
        if c == "REQUESTED":
            return "Đang tạo"
        if c == "PENDING":
            if queue_position > 0:
                return f"Đang chờ (vị trí {queue_position})"
            return "Đang chờ"
        if c == "ACTIVE":
            return "Đang tạo"
        if c == "DOWNLOADING":
            return "Đang tạo"
        if c == "SUCCESSFUL":
            return "Hoàn thành"
        if c == "FAILED":
            return "Lỗi"
        if c == "CANCELED":
            return "Hủy"
        if c == "STOPPED":
            return "Hủy"
        return "Sẵn sàng"

    def _apply_status_color(self, row: int, status_text: str = "") -> None:
        item = self.table.item(int(row), self.COL_STATUS)
        if item is None:
            return
        code = self._status_code(row)
        text = str(status_text or item.text() or "")
        if code in {"FAILED", "STOPPED", "CANCELED"} or "Lỗi" in text or "Hủy" in text:
            color = QColor("#d32f2f")
        elif code in {"SUCCESSFUL"}:
            color = QColor("#2e7d32")
        elif code in {"ACTIVE", "DOWNLOADING", "TOKEN", "REQUESTED"}:
            color = QColor("#ef6c00")
        else:
            color = QColor("#374151")
        item.setForeground(QBrush(color))

    def _refresh_pending_positions(self) -> None:
        pending_rows: list[int] = []
        for r in range(self.table.rowCount()):
            if self._status_code(r) == "PENDING":
                pending_rows.append(r)

        pending_pos = {row: idx + 1 for idx, row in enumerate(pending_rows)}
        for r in range(self.table.rowCount()):
            code = self._status_code(r)
            item = self.table.item(r, self.COL_STATUS)
            if item is None:
                continue
            cur_text = str(item.text() or "")
            if code == "FAILED" and cur_text.startswith("Lỗi"):
                pass
            else:
                item.setText(self._status_text(code, pending_pos.get(r, 0)))
            self._apply_status_color(r)
        self._update_status_summary()
        if not self._loading_status_snapshot:
            self._save_status_snapshot()

    def _normalize_status_code(self, raw: str) -> str:
        text = str(raw or "").upper()
        if "CANCEL" in text or "HUY" in text:
            return "CANCELED"
        if "TOKEN" in text:
            return "TOKEN"
        if "REQUEST" in text or "SUBMIT" in text:
            return "REQUESTED"
        if "QUEUE" in text or "QUEUED" in text:
            return "PENDING"
        if "PENDING" in text:
            return "PENDING"
        if (
            "ACTIVE" in text
            or "RUNNING" in text
            or "PROCESS" in text
            or "PROGRESS" in text
            or "CREATING" in text
            or "GENERATING" in text
            or "STARTED" in text
        ):
            return "ACTIVE"
        if "SUCCESS" in text:
            return "SUCCESSFUL"
        if "FAIL" in text:
            return "FAILED"
        if "DOWNLOADING" in text:
            return "DOWNLOADING"
        return "READY"

    def _prompt_id_of_row(self, row: int) -> str:
        it = self.table.item(int(row), self.COL_PROMPT)
        if it is None:
            return ""
        try:
            return str(it.data(Qt.ItemDataRole.UserRole) or "").strip()
        except Exception:
            return ""

    def _find_row_by_prompt_id(self, prompt_id: str) -> int:
        needle = str(prompt_id or "").strip()
        if not needle:
            return -1
        for r in range(self.table.rowCount() - 1, -1, -1):
            if self._prompt_id_of_row(r) == needle:
                return r
        return -1

    def _collect_runnable_rows(self) -> list[int]:
        rows: list[int] = []
        for r in range(self.table.rowCount()):
            status_code = self._status_code(r)
            if status_code not in {"READY", "FAILED", "STOPPED", "CANCELED"}:
                continue
            prompt_it = self.table.item(r, self.COL_PROMPT)
            prompt_text = (prompt_it.text() if prompt_it is not None else "")
            if str(prompt_text or "").strip():
                rows.append(r)
        return rows

    def _build_project_data_from_rows(self, rows: list[int]) -> dict:
        self._sync_stt_and_prompt_ids()
        items: list[dict] = []
        for r in rows:
            prompt_it = self.table.item(r, self.COL_PROMPT)
            prompt_text = str((prompt_it.text() if prompt_it is not None else "") or "").strip()
            prompt_id = self._prompt_id_of_row(r)
            if not prompt_id:
                prompt_id = self._next_prompt_id()
                if prompt_it is not None:
                    prompt_it.setData(Qt.ItemDataRole.UserRole, prompt_id)
            if prompt_text:
                item_payload = self._row_mode_payload(r)
                item_data = {"id": prompt_id, "description": prompt_text}
                if isinstance(item_payload, dict):
                    for key, value in item_payload.items():
                        if key in {"id", "description"}:
                            continue
                        item_data[key] = value
                items.append(item_data)

        return {
            "prompts": {"text_to_video": items},
            "_use_project_prompts": True,
            "_worker_controls_lifecycle": False,
            "aspect_ratio": str(getattr(self._cfg, "video_aspect_ratio", "9:16") or "9:16"),
            "veo_model": str(getattr(self._cfg, "veo_model", "Veo 3.1 - Fast") or "Veo 3.1 - Fast"),
            "output_count": int(getattr(self._cfg, "output_count", 1) or 1),
        }

    def _resolve_project_name(self) -> str:
        config = SettingsManager.load_config()
        project_name = "default_project"
        if isinstance(config, dict):
            project_name = str(config.get("current_project") or project_name).strip() or project_name
        return project_name

    def _status_snapshot_path(self) -> Path:
        project_dir = WORKFLOWS_DIR / self._resolve_project_name()
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir / "status.json"

    def _row_media_map(self, row: int) -> dict[int, str]:
        it = self.table.item(int(row), self.COL_VIDEO)
        if it is None:
            return {}
        try:
            raw = dict(it.data(Qt.ItemDataRole.UserRole + 1) or {})
        except Exception:
            raw = {}
        out: dict[int, str] = {}
        for key, value in raw.items():
            try:
                idx = int(key)
            except Exception:
                continue
            p = str(value or "").strip()
            if p:
                out[idx] = p
        return out

    def _row_preview_map(self, row: int) -> dict[int, str]:
        it = self.table.item(int(row), self.COL_VIDEO)
        if it is None:
            return {}
        try:
            raw = dict(it.data(Qt.ItemDataRole.UserRole + 4) or {})
        except Exception:
            raw = {}
        out: dict[int, str] = {}
        for key, value in raw.items():
            try:
                idx = int(key)
            except Exception:
                continue
            p = str(value or "").strip()
            if p:
                out[idx] = p
        return out

    def _build_status_snapshot(self) -> dict:
        rows_data: list[dict] = []
        for r in range(self.table.rowCount()):
            stt_item = self.table.item(r, self.COL_STT)
            prompt_item = self.table.item(r, self.COL_PROMPT)
            status_item = self.table.item(r, self.COL_STATUS)
            video_item = self.table.item(r, self.COL_VIDEO)

            prompt_text = str((prompt_item.text() if prompt_item is not None else "") or "").strip()
            prompt_id = self._prompt_id_of_row(r)
            status_code = self._status_code(r)
            status_text = str((status_item.text() if status_item is not None else "") or self._status_text(status_code))
            media_map = self._row_media_map(r)
            preview_map = self._row_preview_map(r)

            selected_output_index = 1
            media_path = ""
            output_count = self._row_output_count(r)
            if video_item is not None:
                try:
                    selected_output_index = int(video_item.data(Qt.ItemDataRole.UserRole + 2) or 1)
                except Exception:
                    selected_output_index = 1
                media_path = str(video_item.data(Qt.ItemDataRole.UserRole) or "").strip()

            if not media_path and media_map:
                media_path = str(media_map.get(selected_output_index) or media_map.get(sorted(media_map.keys())[0]) or "")

            rows_data.append(
                {
                    "row": int(r),
                    "stt": str((stt_item.text() if stt_item is not None else f"{r+1:03d}") or f"{r+1:03d}"),
                    "prompt_id": prompt_id,
                    "prompt": prompt_text,
                    "mode_key": self._row_mode_key(r),
                    "mode_label": self._row_mode_label(r),
                    "mode_name": self._row_mode_label(r),
                    "mode_payload": self._row_mode_payload(r),
                    "status_code": status_code,
                    "status_text": status_text,
                    "output_count": int(output_count),
                    "selected_output_index": int(selected_output_index),
                    "media_map": {str(k): v for k, v in media_map.items()},
                    "preview_map": {str(k): v for k, v in preview_map.items()},
                }
            )

        return {
            "project_name": self._resolve_project_name(),
            "updated_at": int(time.time()),
            "rows": rows_data,
        }

    def _save_status_snapshot(self) -> None:
        if self._loading_status_snapshot:
            return
        try:
            path = self._status_snapshot_path()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._build_status_snapshot(), f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_status_snapshot(self) -> None:
        path = self._status_snapshot_path()
        if not path.exists():
            self._status_loaded = True
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            self._status_loaded = True
            return

        rows = data.get("rows", []) if isinstance(data, dict) else []
        if not isinstance(rows, list):
            rows = []

        self._loading_status_snapshot = True
        try:
            self.table.setRowCount(0)
            for idx, row_data in enumerate(rows):
                if not isinstance(row_data, dict):
                    continue
                prompt_text = str(row_data.get("prompt") or "").strip()
                prompt_id = str(row_data.get("prompt_id") or "").strip()
                row = self.table.rowCount()
                self._add_row(row, prompt_text)

                stt_item = self.table.item(row, self.COL_STT)
                if stt_item is not None:
                    stt_item.setText(str(row_data.get("stt") or f"{idx+1:03d}"))

                prompt_item = self.table.item(row, self.COL_PROMPT)
                if prompt_item is not None and prompt_id:
                    prompt_item.setData(Qt.ItemDataRole.UserRole, prompt_id)

                mode_key = str(row_data.get("mode_key") or self.MODE_TEXT_TO_VIDEO).strip() or self.MODE_TEXT_TO_VIDEO
                mode_payload = row_data.get("mode_payload") if isinstance(row_data.get("mode_payload"), dict) else {}
                self._set_row_mode_meta(row, mode_key, payload=mode_payload)
                self._refresh_prompt_cell(row)

                status_code = str(row_data.get("status_code") or "READY")
                status_text = str(row_data.get("status_text") or self._status_text(status_code))
                self._set_status_code(row, status_code)
                status_item = self.table.item(row, self.COL_STATUS)
                if status_item is not None:
                    status_item.setText(status_text)
                self._apply_status_color(row, status_text)

                video_item = self.table.item(row, self.COL_VIDEO)
                if video_item is None:
                    video_item = QTableWidgetItem("")
                    video_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table.setItem(row, self.COL_VIDEO, video_item)

                output_count = int(row_data.get("output_count") or self._expected_output_count())
                output_count = max(1, min(4, output_count))
                video_item.setData(Qt.ItemDataRole.UserRole + 3, output_count)

                raw_map = row_data.get("media_map") or {}
                media_map: dict[int, str] = {}
                if isinstance(raw_map, dict):
                    for key, value in raw_map.items():
                        try:
                            mk = int(key)
                        except Exception:
                            continue
                        mv = str(value or "").strip()
                        if mv:
                            media_map[mk] = mv
                video_item.setData(Qt.ItemDataRole.UserRole + 1, media_map)

                raw_preview_map = row_data.get("preview_map") or {}
                preview_map: dict[int, str] = {}
                if isinstance(raw_preview_map, dict):
                    for key, value in raw_preview_map.items():
                        try:
                            mk = int(key)
                        except Exception:
                            continue
                        mv = str(value or "").strip()
                        if mv:
                            preview_map[mk] = mv

                selected_idx = int(row_data.get("selected_output_index") or 1)
                if selected_idx not in media_map and media_map:
                    selected_idx = sorted(media_map.keys())[0]
                if selected_idx < 1:
                    selected_idx = 1
                video_item.setData(Qt.ItemDataRole.UserRole + 2, selected_idx)

                media_path = str(row_data.get("media_path") or "").strip()
                if not media_path and media_map:
                    media_path = str(media_map.get(selected_idx) or media_map.get(sorted(media_map.keys())[0]) or "")

                if not preview_map:
                    thumb_path = str(row_data.get("thumbnail_path") or "").strip()
                    if thumb_path and self._is_image_file(thumb_path):
                        preview_map[selected_idx] = thumb_path
                if selected_idx not in preview_map:
                    preview_candidate = media_path
                    if preview_candidate and self._is_image_file(preview_candidate):
                        preview_map[selected_idx] = preview_candidate

                preview_path = str(preview_map.get(selected_idx) or media_path)
                video_item.setData(Qt.ItemDataRole.UserRole, media_path)
                video_item.setText("")
                video_item.setData(Qt.ItemDataRole.UserRole + 4, preview_map)

                self._refresh_video_badges(row)
                self._render_media_preview(row, preview_path)

            self._sync_stt_and_prompt_ids()
        finally:
            self._loading_status_snapshot = False

        self._status_loaded = True
        self._update_empty_state()
        self._update_status_summary()

    def _ensure_status_snapshot_loaded(self) -> None:
        if self._status_loaded:
            return
        self._load_status_snapshot()

    def _update_status_summary(self) -> None:
        done_count = 0
        failed_count = 0
        creating_count = 0
        waiting_count = 0
        creating_codes = {"TOKEN", "REQUESTED", "ACTIVE", "DOWNLOADING"}
        waiting_codes = {"PENDING"}

        for r in range(self.table.rowCount()):
            code = self._status_code(r)
            output_count = self._row_output_count(r)
            media_map = self._row_media_map(r)
            success_for_row = len(media_map)

            done_count += success_for_row

            if code == "FAILED":
                remain = output_count - success_for_row
                failed_count += remain if remain > 0 else 1

            if code in creating_codes:
                remain = output_count - success_for_row
                creating_count += remain if remain > 0 else 1

            if code in waiting_codes:
                remain = output_count - success_for_row
                waiting_count += remain if remain > 0 else 1

        if self.lbl_status_summary is not None:
            self.lbl_status_summary.setText(
                "<span style='color:#16a34a;'>Hoàn thành(" + str(done_count) + ")</span>"
                "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                "<span style='color:#f59e0b;'>Đang tạo(" + str(creating_count) + ")</span>"
                "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                "<span style='color:#2563eb;'>Đang chờ(" + str(waiting_count) + ")</span>"
                "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                "<span style='color:#f87171;'>Lỗi(" + str(failed_count) + ")</span>"
            )

    def _clear_media_for_rows(self, rows: list[int], delete_files: bool = True) -> None:
        cleaned = 0
        for r in rows:
            row = int(r)
            it = self.table.item(row, self.COL_VIDEO)
            if it is None:
                continue

            paths_to_delete: set[str] = set()
            try:
                current = str(it.data(Qt.ItemDataRole.UserRole) or "").strip()
            except Exception:
                current = ""
            if current:
                paths_to_delete.add(current)

            try:
                media_map = dict(it.data(Qt.ItemDataRole.UserRole + 1) or {})
            except Exception:
                media_map = {}
            for value in media_map.values():
                p = str(value or "").strip()
                if p:
                    paths_to_delete.add(p)

            try:
                preview_map = dict(it.data(Qt.ItemDataRole.UserRole + 4) or {})
            except Exception:
                preview_map = {}
            for value in preview_map.values():
                p = str(value or "").strip()
                if p:
                    paths_to_delete.add(p)

            if delete_files:
                for p in paths_to_delete:
                    try:
                        if os.path.isfile(p):
                            os.remove(p)
                    except Exception:
                        pass

            try:
                it.setData(Qt.ItemDataRole.UserRole, "")
                it.setData(Qt.ItemDataRole.UserRole + 1, {})
                it.setData(Qt.ItemDataRole.UserRole + 2, 1)
                it.setData(Qt.ItemDataRole.UserRole + 4, {})
            except Exception:
                pass

            self._refresh_video_badges(row)
            self._render_media_preview(row, "")
            cleaned += 1

        if cleaned > 0 and not self._loading_status_snapshot:
            self._save_status_snapshot()
            self._update_status_summary()

    def start_idea_to_video(self, idea_settings: dict) -> None:
        self._global_stop_requested = False
        if self.isRunning():
            QMessageBox.information(self, "Đang chạy", "Workflow đang chạy, hãy dừng trước khi chạy mới.")
            return

        idea_settings = idea_settings or {}
        idea_text = str(idea_settings.get("idea") or "").strip()
        source_mode = str(idea_settings.get("source_mode") or "manual").strip()
        source_kind = str(idea_settings.get("source_kind") or "auto").strip()
        source_url = str(idea_settings.get("source_url") or "").strip()
        source_pdf_path = str(idea_settings.get("source_pdf_path") or "").strip()
        if source_mode == "link" and not source_url:
            QMessageBox.warning(self, "Thiếu link", "Vui lòng dán link báo/truyện chữ/truyện tranh hoặc link PDF.")
            return
        if source_mode == "pdf" and not source_pdf_path:
            QMessageBox.warning(self, "Thiếu file PDF", "Vui lòng chọn file PDF nguồn.")
            return
        if source_mode not in {"link", "pdf"} and not idea_text:
            QMessageBox.warning(self, "Thiếu kịch bản", "Vui lòng nhập nội dung ở ô Kịch bản/ Ý tưởng.")
            return

        scene_count = int(idea_settings.get("scene_count") or 1)
        style = str(idea_settings.get("style") or "3d_Pixar")
        language = str(idea_settings.get("dialogue_language") or "Tiếng Việt (vi-VN)")
        output_mode = "storytelling_image" if str(idea_settings.get("output_mode") or "").strip() == "storytelling_image" else "video"
        try:
            setattr(self._cfg, "idea_voice_profile", str(idea_settings.get("voice_profile") or "None_NoVoice"))
            setattr(self._cfg, "idea_tts_provider", str(idea_settings.get("tts_provider") or "auto"))
            tts_voice = str(idea_settings.get("tts_voice") or "").strip()
            if tts_voice:
                setattr(self._cfg, "idea_tts_voice", tts_voice)
        except Exception:
            pass

        project_name = self._resolve_project_name()

        mode_label = "Ảnh storytelling" if output_mode == "storytelling_image" else "Video"
        self._append_run_log(f"🚀 Khởi động Idea to Video | project={project_name} | scenes={scene_count} | style={style} | output={mode_label}")
        self._append_run_log("⏳ Đang tạo prompt từ ý tưởng...")
        self._update_empty_state()
        self._idea_worker = _IdeaToVideoWorker(
            project_name=project_name,
            idea_text=idea_text,
            scene_count=scene_count,
            style=style,
            language=language,
            source_mode=source_mode,
            source_kind=source_kind,
            source_url=source_url,
            source_pdf_path=source_pdf_path,
            output_mode=output_mode,
            parent=self,
        )
        self._idea_worker.log_message.connect(self._append_run_log)
        self._idea_worker.completed.connect(self._on_idea_to_video_complete)
        self._idea_worker.start()
        self.runStateChanged.emit(True)

    def start_copy_video(
        self,
        video_path: str,
        target_language: str,
        voice_actor_key: str,
        auto_run: bool,
        style: str = "Tự động nhận diện",
        copy_strength: int = 100,
        user_edit_instruction: str = "",
        video_model: str = "VEO 3",
    ) -> None:
        if not video_path or not os.path.exists(video_path):
            QMessageBox.warning(self, "Loi", f"Khong tim thay video: {video_path}")
            return

        config_data = SettingsManager.load_config()
        account = config_data.get("account1", {}) if isinstance(config_data, dict) else {}
        profile_dir = str(account.get("folder_user_data_get_token") or os.getenv("CHROME_USER_DATA_DIR", "")).strip()
        if not profile_dir:
            profile_dir = os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\User Data\\Default")
        bootstrap_url = str(account.get("URL_GEN_TOKEN") or "https://labs.google/fx/vi/tools/flow").strip()
        copy_strength = _clamp_copy_strength(copy_strength)
        user_edit_instruction = str(user_edit_instruction or "").strip()
        self._append_run_log(
            f"🚀 Khởi động Copy Video | video={os.path.basename(video_path)} | target={normalize_locale(target_language) or 'en-US'} | copy={copy_strength}%"
        )
        if user_edit_instruction:
            self._append_run_log("📝 Có ý tưởng chỉnh sửa riêng; Gemini sẽ áp dụng vào bản sao chép.")
        self._update_empty_state()
        self._clone_worker = _GeminiCloneWorker(
            video_path,
            profile_dir,
            target_language,
            bootstrap_url,
            style,
            copy_strength,
            user_edit_instruction,
            self,
        )
        self._clone_worker.log_message.connect(self._append_run_log)
        self._clone_worker.completed.connect(
            lambda res, voice_key=str(voice_actor_key or "None_NoVoice"), lang=str(target_language or "en-US"), src=str(video_path or ""), ar=bool(auto_run), strength=copy_strength, edit=user_edit_instruction, vmodel=video_model: self._on_copy_video_complete(res, voice_key, lang, ar, src, strength, edit, vmodel)
        )
        self._clone_worker.start()
        self.runStateChanged.emit(True)

    def _on_copy_video_complete(
        self,
        result: dict,
        voice_actor_key: str,
        target_language: str,
        auto_run: bool,
        source_video_path: str,
        copy_strength: int = 100,
        user_edit_instruction: str = "",
        video_model: str = "VEO 3",
    ) -> None:
        self._clone_worker = None
        if not result.get("success"):
            self._append_run_log(f"❌ Lỗi Copy Video: {result.get('message')}")
            self.runStateChanged.emit(False)
            return

        data = result.get("data", {})
        if not isinstance(data, dict):
            self._append_run_log("❌ Gemini không trả về JSON hợp lệ.")
            self.runStateChanged.emit(False)
            return

        self._append_run_log(
            f"✅ Gemini đã phân tích xong: {len(data.get('characters') or [])} nhân vật, {len(data.get('scenes') or [])} scene."
        )
        data["copy_strength_percent"] = _clamp_copy_strength(data.get("copy_strength_percent") or copy_strength)
        user_edit_instruction = str(
            data.get("user_edit_instruction_en")
            or data.get("user_edit_instruction")
            or user_edit_instruction
            or ""
        ).strip()
        if user_edit_instruction:
            data["user_edit_instruction"] = user_edit_instruction
        character_design = data.get("character_design", {}) if isinstance(data.get("character_design"), dict) else {}
        designed_characters = character_design.get("characters") if isinstance(character_design.get("characters"), list) else []
        if designed_characters:
            self._append_run_log(f"🎨 Đã làm giàu hồ sơ nhân vật: {len(designed_characters)} nhân vật.")
        image_payload = self._enqueue_copy_video_character_sheet_prompts(data)
        if image_payload:
            self._append_run_log(f"🖼️ Đã tạo {len(image_payload.get('rows') or [])} prompt ảnh nhân vật. Chờ tạo xong sẽ đổ video.")

        self._populate_character_sync_from_copy_video(data, source_video_path)
        payload = self.enqueue_copy_video_scenes(
            copy_data=data,
            voice_actor_key=voice_actor_key,
            target_language=target_language,
            source_video_path=source_video_path,
            video_model=video_model,
        )
        if payload:
            self._append_run_log("🎬 Đã tạo prompt video.")

        if auto_run:
            self._append_run_log("⚡ Auto-run Copy Video: đưa vào queue render ngay.")
            jobs = []
            if image_payload:
                jobs.append(image_payload)
            if payload:
                jobs.append(payload)
            if jobs:
                try:
                    self.queueJobsRequested.emit(jobs)
                except Exception:
                    pass

        self.runStateChanged.emit(False)



    def _populate_character_sync_from_copy_video(self, copy_data: dict, source_video_path: str) -> None:
        try:
            main_win = self.window()
        except Exception:
            main_win = None
        if main_win is None or not hasattr(main_win, "tab_char_sync"):
            return

        characters = copy_data.get("characters") if isinstance(copy_data.get("characters"), list) else []
        scenes = copy_data.get("scenes") if isinstance(copy_data.get("scenes"), list) else []
        copy_strength = _clamp_copy_strength(copy_data.get("copy_strength_percent") or copy_data.get("copy_strength") or 100)
        use_source_frames = copy_strength > 60
        reference_dir = Path(DATA_GENERAL_DIR) / "copy_video_refs"
        if use_source_frames:
            reference_dir.mkdir(parents=True, exist_ok=True)
        duration_sec = self._probe_video_duration_seconds(source_video_path)
        total_scenes = max(1, len(scenes))

        character_items: list[dict] = []
        prompt_lines: list[str] = []
        for scene in scenes:
            if not isinstance(scene, dict):
                continue
            prompt_text = ", ".join(
                [
                    str(scene.get("video_prompt_en") or "").strip(),
                    str(scene.get("dialogue_target") or "").strip(),
                ]
            ).strip(", ")
            if prompt_text:
                prompt_lines.append(prompt_text)

        for idx, character in enumerate(characters, start=1):
            if not isinstance(character, dict):
                continue
            character_id = str(character.get("character_id") or f"char_{idx:02d}").strip()
            identity_lock = str(character.get("identity_lock_en") or "").strip()
            display_name = str(character.get("display_name") or character_id).strip() or character_id
            if not character_id:
                continue
            frame_path = ""
            if use_source_frames:
                timestamp = self._estimate_copy_video_timestamp(character_id, scenes, duration_sec, total_scenes, idx)
                output_path = reference_dir / f"{Path(source_video_path).stem}_{character_id}.png"
                frame_path = self._extract_video_frame(source_video_path, float(timestamp), output_path)
            character_items.append(
                {
                    "character_id": character_id,
                    "name": display_name,
                    "path": frame_path,
                    "identity_lock": identity_lock,
                }
            )

        try:
            main_win.tab_char_sync.replace_characters(character_items)
            main_win.tab_char_sync.set_prompts(prompt_lines)
        except Exception:
            pass

    def _enqueue_copy_video_character_sheet_prompts(self, copy_data: dict) -> dict | None:
        characters = copy_data.get("characters") if isinstance(copy_data.get("characters"), list) else []
        items: list[dict] = []
        for idx, character in enumerate(characters, start=1):
            if not isinstance(character, dict):
                continue
            character_id = str(character.get("character_id") or f"char_{idx:02d}").strip()
            character_name = str(character.get("display_name") or character_id).strip() or character_id
            
            # Tạo ảnh nhân vật bằng toàn bộ cấu trúc JSON
            prompt_text = json.dumps(character, ensure_ascii=True, indent=2)
            if not prompt_text or prompt_text == "{}":
                continue
            items.append(
                {
                    "description": prompt_text,
                    "aspect_ratio": "16:9",
                    "source_type": "copy_video_character_sheet",
                    "character_id": character_id,
                    "character_name": character_name,
                }
            )
        if not items:
            return None
        return self.enqueue_generate_image_from_prompts(items)

    def _update_character_sync_sheet_preview(self, row: int, image_path: str) -> None:
        new_path = str(image_path or "").strip()
        if row < 0 or not new_path or not os.path.isfile(new_path):
            return

        payload = self._row_mode_payload(int(row))
        if str(payload.get("source_type") or "").strip() != "copy_video_character_sheet":
            return

        try:
            main_win = self.window()
        except Exception:
            main_win = None
        if main_win is None or not hasattr(main_win, "tab_char_sync"):
            return

        character_id = str(payload.get("character_id") or "").strip()
        character_name = str(payload.get("character_name") or "").strip()
        identity_lock = str(payload.get("identity_lock") or "").strip()

        try:
            updated = main_win.tab_char_sync.update_character_image(
                new_path,
                character_id=character_id,
                character_name=character_name,
                identity_lock=identity_lock,
            )
        except Exception:
            updated = False

        if updated:
            label = character_name or character_id or f"row {int(row) + 1}"
            self._append_run_log(f"🧩 Đã cập nhật ảnh sheet nhân vật: {label}")

    def _estimate_copy_video_timestamp(
        self,
        character_id: str,
        scenes: list[dict],
        duration_sec: float,
        total_scenes: int,
        fallback_index: int,
    ) -> float:
        for idx, scene in enumerate(scenes):
            if not isinstance(scene, dict):
                continue
            scene_character_ids = [str(x).strip() for x in (scene.get("character_ids") or []) if str(x).strip()]
            if character_id not in scene_character_ids:
                continue
            try:
                start_sec = float(scene.get("start_sec"))
                end_sec = float(scene.get("end_sec"))
                if end_sec > start_sec >= 0:
                    return max(0.0, (start_sec + end_sec) / 2.0)
            except Exception:
                pass
            if duration_sec > 0:
                return max(0.0, duration_sec * ((idx + 0.5) / max(1, total_scenes)))
            return float(max(0.0, idx * 1.5))
        if duration_sec > 0:
            return max(0.0, duration_sec * ((fallback_index - 0.5) / max(1, total_scenes)))
        return float(max(0.0, (fallback_index - 1) * 1.5))

    def _probe_video_duration_seconds(self, video_path: str) -> float:
        try:
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            result = subprocess.run(
                [ffmpeg_exe, "-i", str(video_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                **_win_hidden_kwargs(),
            )
            text = f"{result.stdout}\n{result.stderr}"
            match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
            if not match:
                return 0.0
            hours = float(match.group(1))
            minutes = float(match.group(2))
            seconds = float(match.group(3))
            return max(0.0, (hours * 3600.0) + (minutes * 60.0) + seconds)
        except Exception:
            return 0.0

    def _extract_video_frame(self, video_path: str, timestamp_sec: float, output_path: Path) -> str:
        try:
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                [
                    ffmpeg_exe,
                    "-y",
                    "-ss",
                    f"{max(0.0, float(timestamp_sec)):.3f}",
                    "-i",
                    str(video_path),
                    "-frames:v",
                    "1",
                    str(output_path),
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                **_win_hidden_kwargs(),
            )
            if output_path.is_file():
                return str(output_path)
        except Exception:
            pass
        return ""

    def start_clone_video(self, video_path: str, voice_profile: str, auto_run: bool) -> None:
        if not video_path or not os.path.exists(video_path):
            QMessageBox.warning(self, "Lỗi", f"Không tìm thấy video: {video_path}")
            return

        profile_dir = str(os.getenv("CHROME_USER_DATA_DIR", "")) or os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\User Data\\Default")

        self._append_run_log(f"🚀 Khởi động Clone Video (Pro Max) | video={os.path.basename(video_path)}")
        self._update_empty_state()
        self._clone_worker = _GeminiCloneWorker(video_path, profile_dir, "en-US", "", "Tự động nhận diện", 100, "", self)
        self._clone_worker.log_message.connect(self._append_run_log)
        self._clone_worker.completed.connect(lambda res: self._on_clone_complete(res, voice_profile, auto_run))
        self._clone_worker.start()
        self.runStateChanged.emit(True)

    def _on_clone_complete(self, result: dict, voice_profile: str, auto_run: bool) -> None:
        self._clone_worker = None
        if not result.get("success"):
            self._append_run_log(f"❌ Lỗi Clone: {result.get('message')}")
            self.runStateChanged.emit(False)
            return

        data = result.get("data", {})
        self._append_run_log("✅ Phân tích video thành công!")

        # 1. Sync Character
        identity = data.get("identity_lock", "")
        if identity:
            self._append_run_log(f"👤 Character ID: {identity}")
            # Here we should ideally have a way to inject into tab_char_sync
            # For now, let's just log it or find the tab via parent
            try:
                main_win = self.window()
                if hasattr(main_win, "tab_char_sync"):
                    main_win.tab_char_sync.add_character("Cloned_Char", "", identity)
            except Exception:
                pass

        # 2. Populate DataGrid (Status Table)
        script = data.get("vietnamese_script", "")
        prompt = data.get("video_prompt", "")
        
        # Inject voice into prompt
        if voice_profile and voice_profile != "None_NoVoice":
            prompt = f"{prompt} | speaking: \"{script}\" using {voice_profile}"
        
        row = self._add_status_row(
            prompt=prompt,
            mode_key=self.MODE_TEXT_TO_VIDEO
        )
        self._append_run_log(f"📝 Đã thêm kịch bản vào dòng {row+1}")

        if auto_run:
            self._append_run_log("⚡ Auto Run enabled: Bắt đầu render...")
            self._start_text_to_video_rows([row])
        else:
            self.runStateChanged.emit(False)

    def _on_idea_to_video_complete(self, result: dict) -> None:
        self._idea_worker = None

        if self._global_stop_requested:
            self._append_run_log("🛑 Bỏ qua callback Idea to Video vì đã nhận lệnh dừng toàn bộ")
            self.runStateChanged.emit(False)
            return

        ok = bool((result or {}).get("success"))
        msg = str((result or {}).get("message") or "")
        if msg:
            self._append_run_log(msg)

        if not ok:
            self.runStateChanged.emit(False)
            return

        prompts_data = (result or {}).get("prompts")
        prompt_texts: list[str] = []
        if isinstance(prompts_data, list):
            for item in prompts_data:
                if isinstance(item, dict):
                    text = str(item.get("prompt") or item.get("description") or "").strip()
                    if text:
                        prompt_texts.append(text)

        if not prompt_texts:
            self._append_run_log("⚠️ Idea to Video không trả về prompt hợp lệ.")
            self.runStateChanged.emit(False)
            return

        output_mode = "storytelling_image" if str((result or {}).get("_output_mode") or "").strip() == "storytelling_image" else "video"
        if output_mode == "storytelling_image":
            storytelling_items = [
                self._storytelling_item_from_prompt(prompt_text, idx)
                for idx, prompt_text in enumerate(prompt_texts, start=1)
            ]
            payload = self.enqueue_generate_image_from_prompts(storytelling_items)
            if not payload:
                self.runStateChanged.emit(False)
                return
            self._append_run_log(f"✅ Idea to Video tạo {len(storytelling_items)} cảnh. Bắt đầu tạo ảnh Storytelling...")
            started = self.start_queued_job(str(payload.get("mode_key") or ""), list(payload.get("rows") or []))
            if not started:
                self.runStateChanged.emit(False)
            return

        idea_voice_key = str(getattr(self._cfg, "idea_voice_profile", "None_NoVoice") or "None_NoVoice")
        idea_voice_profile_text = get_voice_profile_text(idea_voice_key)
        video_prompt_texts = [
            self._idea_video_prompt_from_prompt_text(prompt_text, idx, idea_voice_profile_text)
            for idx, prompt_text in enumerate(prompt_texts, start=1)
        ]
        self._append_run_log(f"✅ Idea to Video tạo {len(video_prompt_texts)} prompt tiếng Anh chuẩn VEO. Bắt đầu chạy Text to Video...")
        self.start_text_to_video(video_prompt_texts)

    def _start_text_to_video_rows(self, rows: list[int]) -> bool:
        if not rows:
            return False

        self._snapshot_output_count_for_rows(rows)

        project_name = self._resolve_project_name()
        project_data = self._build_project_data_from_rows(rows)
        
        voice_key = str(getattr(self._cfg, "voice_profile", "None_NoVoice") or "None_NoVoice")
        voice_direction = VOICE_JSON.get(voice_key, {}).get("voice_profile", "")
        project_data["voice_profile"] = voice_direction

        prompts = project_data.get("prompts", {}).get("text_to_video", [])
        if not prompts:
            QMessageBox.warning(self, "Không có prompt", "Không có prompt hợp lệ trong bảng status.")
            return False

        try:
            self._append_run_log(f"🚀 Khởi động workflow Text to Video | project={project_name} | prompts={len(prompts)}")
            self._workflow = TextToVideoWorkflow(project_name=project_name, project_data=project_data, parent=self)
            self._workflow.log_message.connect(self._on_workflow_log)
            self._workflow.video_updated.connect(self._on_video_updated)
            self._workflow.automation_complete.connect(self._on_workflow_complete)
            self._workflow.start()
            self._workflows.append(self._workflow)
        except Exception as exc:
            self._workflow = None
            self._append_run_log(f"❌ Không thể khởi động workflow: {exc}")
            QMessageBox.critical(self, "Lỗi workflow", f"Không thể khởi động workflow: {exc}")
            return False

        for r in rows:
            self._set_status_code(r, "PENDING")
        self._refresh_pending_positions()
        self.runStateChanged.emit(True)
        return True

    def _start_grok_text_to_video_rows(self, rows: list[int]) -> bool:
        if not rows:
            return False

        self._set_output_count_for_rows(rows, 1)

        prompts: list[str] = []
        prompt_ids: list[str] = []
        for r in rows:
            prompt_item = self.table.item(int(r), self.COL_PROMPT)
            prompt_text = str((prompt_item.text() if prompt_item is not None else "") or "").strip()
            if not prompt_text:
                continue
            prompts.append(prompt_text)
            prompt_ids.append(self._prompt_id_of_row(int(r)) or str(int(r) + 1))

        if not prompts:
            QMessageBox.warning(self, "Không có prompt", "Không có prompt GROK hợp lệ trong bảng status.")
            return False

        aspect_ratio = str(getattr(self._cfg, "video_aspect_ratio", "9:16") or "9:16")
        grok_video_length_seconds = int(getattr(self._cfg, "grok_video_length_seconds", 6) or 6)
        grok_video_resolution = str(getattr(self._cfg, "grok_video_resolution", "480p") or "480p")
        grok_account_type = str(getattr(self._cfg, "grok_account_type", "SUPER") or "SUPER").strip().upper()
        if grok_account_type == "ULTRA":
            grok_account_type = "SUPER"
        if grok_account_type == "NORMAL":
            if grok_video_length_seconds != 6 or grok_video_resolution != "480p":
                self._append_run_log("ℹ️ GROK NORMAL: ép cấu hình 6 giây và 480p")
            grok_video_length_seconds = 6
            grok_video_resolution = "480p"
        output_dir = str(getattr(self._cfg, "video_output_dir", "") or "").strip()
        max_concurrency = max(1, int(getattr(self._cfg, "grok_multi_video", getattr(self._cfg, "multi_video", 5)) or 5))
        offscreen = True

        try:
            self._append_run_log(
                f"🚀 Khởi động workflow GROK Text to Video | prompts={len(prompts)} | max={max_concurrency}"
            )
            grok_voice_key = str(getattr(self._cfg, "grok_voice_profile", "None_NoVoice") or "None_NoVoice")
            grok_voice_direction = VOICE_JSON.get(grok_voice_key, {}).get("voice_profile", "")

            worker = GrokTextToVideoWorker(
                prompts=prompts,
                prompt_ids=prompt_ids,
                aspect_ratio=aspect_ratio,
                video_length_seconds=grok_video_length_seconds,
                resolution_name=grok_video_resolution,
                voice_direction=grok_voice_direction,
                output_dir=output_dir,
                max_concurrency=max_concurrency,
                offscreen_chrome=offscreen,
                parent=self,
            )
            worker.log_message.connect(self._append_run_log)
            worker.status_updated.connect(self._on_grok_status_updated)
            worker.video_updated.connect(self._on_video_updated)
            worker.automation_complete.connect(self._on_workflow_complete)
            worker.start()
            self._workflow = worker
            self._workflows.append(worker)
        except Exception as exc:
            self._workflow = None
            self._append_run_log(f"❌ Không thể khởi động GROK workflow: {exc}")
            QMessageBox.critical(self, "Lỗi workflow", f"Không thể khởi động GROK workflow: {exc}")
            return False

        for r in rows:
            self._set_status_code(int(r), "PENDING")
        self._refresh_pending_positions()
        self.runStateChanged.emit(True)
        return True

    def _on_grok_status_updated(self, payload: dict) -> None:
        if not isinstance(payload, dict):
            return
        prompt_id = str(payload.get("prompt_id") or "").strip()
        row = self._find_row_by_prompt_id(prompt_id) if prompt_id else -1
        if row < 0:
            return

        current_code = self._status_code(row)
        if current_code in {"SUCCESSFUL", "FAILED", "CANCELED", "STOPPED"}:
            return

        progress = payload.get("progress")
        status_text = str(payload.get("status_text") or "").strip()
        low = status_text.lower()

        if isinstance(progress, int):
            self._set_video_progress_text(row, int(progress))
            self._set_row_status_detail(row, "ACTIVE", "Đang tạo")

        if "lỗi" in low or low == "error" or low.startswith("error"):
            self._set_row_status_detail(row, "FAILED", self._format_failed_status_text("GROK_ERROR", status_text))
            self._try_finalize_grok_batch_now()
            return
        if "hoàn thành" in low or "hoan thanh" in low or "done" in low or "complete" in low:
            self._set_row_status_detail(row, "SUCCESSFUL", "Hoàn thành")
            return
        if "tải" in low or "download" in low:
            self._set_row_status_detail(row, "DOWNLOADING", "Đang tải video")
            return
        if "xếp hàng" in low:
            self._set_row_status_detail(row, "PENDING", "Đang chờ")
            return
        if status_text:
            self._set_row_status_detail(row, "ACTIVE", "Đang tạo")

        self._try_finalize_grok_batch_now()

    def _start_grok_image_to_video_rows(self, rows: list[int]) -> bool:
        if not rows:
            return False

        self._set_output_count_for_rows(rows, 1)

        items: list[dict] = []
        prompt_ids: list[str] = []
        for r in rows:
            payload = self._row_mode_payload(int(r))
            image_link = str(payload.get("image_link") or "").strip()
            if not image_link:
                continue
            prompt_item = self.table.item(int(r), self.COL_PROMPT)
            prompt_text = str((prompt_item.text() if prompt_item is not None else "") or "").strip()
            items.append({"image_path": image_link, "prompt": prompt_text})
            prompt_ids.append(self._prompt_id_of_row(int(r)) or str(int(r) + 1))

        if not items:
            QMessageBox.warning(self, "Không có dữ liệu", "Không có dữ liệu GROK Image to Video hợp lệ trong bảng status.")
            return False

        aspect_ratio = str(getattr(self._cfg, "video_aspect_ratio", "9:16") or "9:16")
        grok_video_length_seconds = int(getattr(self._cfg, "grok_video_length_seconds", 6) or 6)
        grok_video_resolution = str(getattr(self._cfg, "grok_video_resolution", "480p") or "480p")
        grok_account_type = str(getattr(self._cfg, "grok_account_type", "SUPER") or "SUPER").strip().upper()
        if grok_account_type == "ULTRA":
            grok_account_type = "SUPER"
        if grok_account_type == "NORMAL":
            if grok_video_length_seconds != 6 or grok_video_resolution != "480p":
                self._append_run_log("ℹ️ GROK NORMAL: ép cấu hình 6 giây và 480p")
            grok_video_length_seconds = 6
            grok_video_resolution = "480p"
        output_dir = str(getattr(self._cfg, "video_output_dir", "") or "").strip()
        max_concurrency = max(1, int(getattr(self._cfg, "grok_multi_video", getattr(self._cfg, "multi_video", 5)) or 5))
        offscreen = True

        try:
            self._append_run_log(
                f"🚀 Khởi động workflow GROK Image to Video | jobs={len(items)} | max={max_concurrency}"
            )
            grok_voice_key = str(getattr(self._cfg, "grok_voice_profile", "None_NoVoice") or "None_NoVoice")
            grok_voice_direction = VOICE_JSON.get(grok_voice_key, {}).get("voice_profile", "")

            worker = GrokImageToVideoWorker(
                items=items,
                prompt_ids=prompt_ids,
                aspect_ratio=aspect_ratio,
                video_length_seconds=grok_video_length_seconds,
                resolution_name=grok_video_resolution,
                voice_direction=grok_voice_direction,
                output_dir=output_dir,
                max_concurrency=max_concurrency,
                offscreen_chrome=offscreen,
                parent=self,
            )
            worker.log_message.connect(self._append_run_log)
            worker.status_updated.connect(self._on_grok_status_updated)
            worker.video_updated.connect(self._on_video_updated)
            worker.automation_complete.connect(self._on_workflow_complete)
            worker.start()
            self._workflow = worker
            self._workflows.append(worker)
        except Exception as exc:
            self._workflow = None
            self._append_run_log(f"❌ Không thể khởi động GROK Image to Video: {exc}")
            QMessageBox.critical(self, "Lỗi workflow", f"Không thể khởi động GROK Image to Video: {exc}")
            return False

        for r in rows:
            self._set_status_code(int(r), "PENDING")
        self._refresh_pending_positions()
        self.runStateChanged.emit(True)
        return True

    def _start_image_to_video_rows(self, rows: list[int], normalized_mode: str) -> bool:
        if not rows:
            return False

        clean_items: list[dict] = []
        prompt_key = "image_to_video_start_end" if normalized_mode == "start_end" else "image_to_video"
        for r in rows:
            prompt_item = self.table.item(int(r), self.COL_PROMPT)
            prompt_text = str((prompt_item.text() if prompt_item is not None else "") or "").strip()
            payload = self._row_mode_payload(int(r))
            if normalized_mode == "start_end":
                start_image_link = str(payload.get("start_image_link") or "").strip()
                end_image_link = str(payload.get("end_image_link") or "").strip()
                if not (start_image_link and end_image_link and prompt_text):
                    continue
                clean_items.append(
                    {
                        "id": self._prompt_id_of_row(int(r)) or str(int(r) + 1),
                        "prompt": prompt_text,
                        "start_image_link": start_image_link,
                        "end_image_link": end_image_link,
                    }
                )
            else:
                image_link = str(payload.get("image_link") or "").strip()
                if not (image_link and prompt_text):
                    continue
                clean_items.append(
                    {
                        "id": self._prompt_id_of_row(int(r)) or str(int(r) + 1),
                        "prompt": prompt_text,
                        "image_link": image_link,
                    }
                )

        if not clean_items:
            return False

        self._snapshot_output_count_for_rows(rows)
        project_name = self._resolve_project_name()
        project_data = {
            "prompts": {prompt_key: clean_items},
            "_use_project_prompts": True,
            "_worker_controls_lifecycle": False,
            "i2v_mode": normalized_mode,
            "aspect_ratio": str(getattr(self._cfg, "video_aspect_ratio", "9:16") or "9:16"),
            "veo_model": str(getattr(self._cfg, "veo_model", "Veo 3.1 - Fast") or "Veo 3.1 - Fast"),
            "output_count": int(getattr(self._cfg, "output_count", 1) or 1),
            "video_output_dir": str(getattr(self._cfg, "video_output_dir", "") or "").strip(),
        }

        try:
            from A_workflow_image_to_video import ImageToVideoWorkflow

            mode_label = "Ảnh Đầu - Ảnh Cuối" if normalized_mode == "start_end" else "Ảnh"
            self._append_run_log(
                f"🚀 Khởi động workflow Image to Video ({mode_label}) | project={project_name} | prompts={len(clean_items)}"
            )
            self._workflow = ImageToVideoWorkflow(project_name=project_name, project_data=project_data, parent=self)
            self._workflow.log_message.connect(self._on_workflow_log)
            self._workflow.video_updated.connect(self._on_video_updated)
            self._workflow.automation_complete.connect(self._on_workflow_complete)
            self._workflow.start()
            self._workflows.append(self._workflow)
        except Exception as exc:
            self._workflow = None
            self._append_run_log(f"❌ Không thể khởi động workflow Image to Video: {exc}")
            QMessageBox.critical(self, "Lỗi workflow", f"Không thể khởi động workflow Image to Video: {exc}")
            return False

        for r in rows:
            self._set_status_code(int(r), "PENDING")
        self._refresh_pending_positions()
        self.runStateChanged.emit(True)
        return True

    def _start_generate_image_rows(self, rows: list[int]) -> bool:
        if not rows:
            return False

        clean_items: list[dict] = []
        aspect_ratio_override = ""
        for r in rows:
            prompt_item = self.table.item(int(r), self.COL_PROMPT)
            prompt_text = str((prompt_item.text() if prompt_item is not None else "") or "").strip()
            if not prompt_text:
                continue
            payload = self._row_mode_payload(int(r))
            item_data = {"id": self._prompt_id_of_row(int(r)) or str(int(r) + 1), "description": prompt_text}
            if isinstance(payload, dict):
                for key, value in payload.items():
                    if key in {"id", "description", "prompt"}:
                        continue
                    item_data[key] = value
            clean_items.append(item_data)
            if not aspect_ratio_override:
                aspect_ratio_override = str(payload.get("aspect_ratio") or "").strip() if isinstance(payload, dict) else ""

        if not clean_items:
            return False

        storytelling_batch = any(self._is_storytelling_row(int(r)) for r in rows)
        if storytelling_batch:
            self._set_output_count_for_rows(rows, 1)
        else:
            self._snapshot_output_count_for_rows(rows)
        project_name = self._resolve_project_name()
        project_data = {
            "prompts": {"text_to_video": clean_items},
            "_use_project_prompts": True,
            "_worker_controls_lifecycle": True,
            "aspect_ratio": str(aspect_ratio_override or getattr(self._cfg, "video_aspect_ratio", "9:16") or "9:16"),
            "veo_model": str(getattr(self._cfg, "veo_model", "Veo 3.1 - Fast") or "Veo 3.1 - Fast"),
            "output_count": 1 if storytelling_batch else int(getattr(self._cfg, "output_count", 1) or 1),
            "video_output_dir": str(getattr(self._cfg, "video_output_dir", "") or "").strip(),
        }

        try:
            from A_workflow_generate_image import GenerateImageWorkflow

            self._append_run_log(
                f"🚀 Khởi động workflow Tạo Ảnh từ Prompt | project={project_name} | prompts={len(clean_items)}"
            )
            self._workflow = GenerateImageWorkflow(project_name=project_name, project_data=project_data, parent=self)
            self._workflow.log_message.connect(self._on_workflow_log)
            self._workflow.video_updated.connect(self._on_video_updated)
            self._workflow.automation_complete.connect(self._on_workflow_complete)
            self._workflow.start()
            self._workflows.append(self._workflow)
        except Exception as exc:
            self._workflow = None
            self._append_run_log(f"❌ Không thể khởi động workflow Tạo Ảnh: {exc}")
            QMessageBox.critical(self, "Lỗi workflow", f"Không thể khởi động workflow Tạo Ảnh: {exc}")
            return False

        for r in rows:
            self._set_status_code(int(r), "PENDING")
        self._refresh_pending_positions()
        self.runStateChanged.emit(True)
        return True

    def _start_generate_image_reference_rows(self, rows: list[int], shared_characters: list[dict] | None = None) -> bool:
        if not rows:
            return False

        prompts: list[dict] = []
        for r in rows:
            prompt_item = self.table.item(int(r), self.COL_PROMPT)
            prompt_text = str((prompt_item.text() if prompt_item is not None else "") or "").strip()
            if not prompt_text:
                continue
            prompts.append({"id": self._prompt_id_of_row(int(r)) or str(int(r) + 1), "prompt": prompt_text})

        characters = list(shared_characters or [])
        if not characters:
            for r in rows:
                payload = self._row_mode_payload(int(r))
                cand = payload.get("characters") if isinstance(payload, dict) else None
                if isinstance(cand, list) and cand:
                    characters = [x for x in cand if isinstance(x, dict)]
                    break

        clean_characters: list[dict] = []
        for ch in characters:
            name = str(ch.get("name") or "").strip() if isinstance(ch, dict) else ""
            path = str(ch.get("path") or "").strip() if isinstance(ch, dict) else ""
            if name and path:
                clean_characters.append({"name": name, "path": path})

        if not prompts or not clean_characters:
            return False

        project_name = self._resolve_project_name()
        project_data = {
            "prompts": {"create_image_reference": prompts},
            "characters": clean_characters,
            "image_mode": "reference",
            "_use_project_prompts": True,
            "_worker_controls_lifecycle": True,
            "aspect_ratio": str(getattr(self._cfg, "video_aspect_ratio", "9:16") or "9:16"),
            "veo_model": str(getattr(self._cfg, "veo_model", "Veo 3.1 - Fast") or "Veo 3.1 - Fast"),
            "create_image_model": str(getattr(self._cfg, "create_image_model", "Imagen 4") or "Imagen 4"),
            "output_count": int(getattr(self._cfg, "output_count", 1) or 1),
            "video_output_dir": str(getattr(self._cfg, "video_output_dir", "") or "").strip(),
        }

        try:
            from A_workflow_image_to_image import GenerateImageWorkflow

            self._append_run_log(
                f"🚀 Khởi động workflow Tạo Ảnh từ Ảnh Tham Chiếu | project={project_name} | prompts={len(prompts)} | refs={len(clean_characters)}"
            )
            self._workflow = GenerateImageWorkflow(project_name=project_name, project_data=project_data, parent=self)
            self._workflow.log_message.connect(self._on_workflow_log)
            self._workflow.video_updated.connect(self._on_video_updated)
            self._workflow.automation_complete.connect(self._on_workflow_complete)
            self._workflow.start()
            self._workflows.append(self._workflow)
        except Exception as exc:
            self._workflow = None
            self._append_run_log(f"❌ Không thể khởi động workflow Tạo Ảnh từ Ảnh Tham Chiếu: {exc}")
            QMessageBox.critical(self, "Lỗi workflow", f"Không thể khởi động workflow Tạo Ảnh từ Ảnh Tham Chiếu: {exc}")
            return False

        for r in rows:
            self._set_status_code(int(r), "PENDING")
        self._refresh_pending_positions()
        self.runStateChanged.emit(True)
        return True

    def _start_character_sync_rows(self, rows: list[int], shared_characters: list[dict] | None = None) -> bool:
        if not rows:
            return False

        prompts: list[dict] = []
        for r in rows:
            prompt_item = self.table.item(int(r), self.COL_PROMPT)
            prompt_text = str((prompt_item.text() if prompt_item is not None else "") or "").strip()
            if not prompt_text:
                continue
            prompts.append({"id": self._prompt_id_of_row(int(r)) or str(int(r) + 1), "prompt": prompt_text})

        characters = list(shared_characters or [])
        if not characters:
            for r in rows:
                payload = self._row_mode_payload(int(r))
                cand = payload.get("characters") if isinstance(payload, dict) else None
                if isinstance(cand, list) and cand:
                    characters = [x for x in cand if isinstance(x, dict)]
                    break

        clean_characters: list[dict] = []
        for ch in characters:
            name = str(ch.get("name") or "").strip() if isinstance(ch, dict) else ""
            path = str(ch.get("path") or "").strip() if isinstance(ch, dict) else ""
            if name and path:
                clean_characters.append({"name": name, "path": path})

        if not prompts or not clean_characters:
            return False

        project_name = self._resolve_project_name()
        project_data = {
            "prompts": {"character_sync": prompts},
            "characters": clean_characters,
            "_use_project_prompts": True,
            "_worker_controls_lifecycle": True,
            "aspect_ratio": str(getattr(self._cfg, "video_aspect_ratio", "9:16") or "9:16"),
            "veo_model": str(getattr(self._cfg, "veo_model", "Veo 3.1 - Fast") or "Veo 3.1 - Fast"),
            "output_count": int(getattr(self._cfg, "output_count", 1) or 1),
            "video_output_dir": str(getattr(self._cfg, "video_output_dir", "") or "").strip(),
        }

        try:
            from A_workflow_sync_chactacter import CharacterSyncWorkflow

            self._append_run_log(
                f"🚀 Khởi động workflow Đồng bộ nhân vật | project={project_name} | prompts={len(prompts)} | characters={len(clean_characters)}"
            )
            self._workflow = CharacterSyncWorkflow(project_name=project_name, project_data=project_data, parent=self)
            self._workflow.log_message.connect(self._on_workflow_log)
            self._workflow.video_updated.connect(self._on_video_updated)
            self._workflow.automation_complete.connect(self._on_workflow_complete)
            self._workflow.start()
            self._workflows.append(self._workflow)
        except Exception as exc:
            self._workflow = None
            self._append_run_log(f"❌ Không thể khởi động workflow Đồng bộ nhân vật: {exc}")
            QMessageBox.critical(self, "Lỗi workflow", f"Không thể khởi động workflow Đồng bộ nhân vật: {exc}")
            return False

        for r in rows:
            self._set_status_code(int(r), "PENDING")
        self._refresh_pending_positions()
        self.runStateChanged.emit(True)
        return True

    def _start_rows_by_mode(self, rows: list[int]) -> None:
        if not rows:
            return

        self._sync_stt_and_prompt_ids()
        grouped: dict[str, list[int]] = {}
        for r in rows:
            mode_key = self._row_mode_key(int(r))
            grouped.setdefault(mode_key, []).append(int(r))

        queue: list[tuple[str, list[int]]] = []
        queue_jobs: list[dict] = []
        all_valid_rows: list[int] = []
        skipped_messages: list[str] = []
        for mode_key, mode_rows in grouped.items():
            valid_rows: list[int] = []
            for r in mode_rows:
                prompt_item = self.table.item(int(r), self.COL_PROMPT)
                prompt_text = str((prompt_item.text() if prompt_item is not None else "") or "").strip()
                payload = self._row_mode_payload(int(r))
                if mode_key == self.MODE_IMAGE_TO_VIDEO_SINGLE and not str(payload.get("image_link") or "").strip():
                    continue
                if mode_key == self.MODE_GROK_IMAGE_TO_VIDEO and not str(payload.get("image_link") or "").strip():
                    continue
                if mode_key == self.MODE_IMAGE_TO_VIDEO_START_END:
                    if not str(payload.get("start_image_link") or "").strip() or not str(payload.get("end_image_link") or "").strip():
                        continue
                if mode_key in {self.MODE_TEXT_TO_VIDEO, self.MODE_GROK_TEXT_TO_VIDEO, self.MODE_CREATE_IMAGE_PROMPT, self.MODE_COPY_VIDEO} and not prompt_text:
                    continue
                if mode_key == self.MODE_CREATE_IMAGE_REFERENCE:
                    chars = payload.get("characters") if isinstance(payload, dict) else None
                    if not prompt_text or not isinstance(chars, list) or not chars:
                        continue
                valid_rows.append(int(r))
            if valid_rows:
                queue.append((mode_key, valid_rows))
                all_valid_rows.extend(valid_rows)
            else:
                skipped_messages.append(f"{self._mode_label(mode_key)}: thiếu dữ liệu")

        if not queue:
            QMessageBox.warning(self, "Thiếu dữ liệu", "Không có dòng hợp lệ để tạo lại theo mode đã lưu.")
            return

        prev_codes: dict[int, str] = {}
        for r in all_valid_rows:
            rr = int(r)
            prev_codes[rr] = self._status_code(rr)
            self._set_status_code(rr, "PENDING")
        self._refresh_pending_positions()

        self._retry_mode_queue = []
        for mode_key, mode_rows in queue:
            queue_jobs.append(
                {
                    "mode_key": str(mode_key),
                    "rows": [int(r) for r in mode_rows],
                    "label": self._mode_label(str(mode_key)),
                }
            )

        started = bool(queue_jobs)
        if started:
            try:
                self.queueJobsRequested.emit(queue_jobs)
            except Exception:
                started = False

        if skipped_messages:
            self._append_run_log("⚠️ Bỏ qua một số dòng: " + " | ".join(skipped_messages))

        if not started:
            for r, code in prev_codes.items():
                self._set_status_code(int(r), str(code or "READY"))
            self._refresh_pending_positions()
            QMessageBox.warning(self, "Không thể chạy", "Không thể khởi động lại các dòng đã chọn theo mode đã lưu.")

    def _start_mode_group(self, mode_key: str, rows: list[int]) -> bool:
        key = str(mode_key or "").strip() or self.MODE_TEXT_TO_VIDEO
        if key == self.MODE_TEXT_TO_VIDEO:
            return self._start_text_to_video_rows(rows)
        if key == self.MODE_COPY_VIDEO:
            return self._start_text_to_video_rows(rows)
        if key == self.MODE_GROK_TEXT_TO_VIDEO:
            return self._start_grok_text_to_video_rows(rows)
        if key == self.MODE_GROK_IMAGE_TO_VIDEO:
            return self._start_grok_image_to_video_rows(rows)
        if key == self.MODE_IMAGE_TO_VIDEO_SINGLE:
            return self._start_image_to_video_rows(rows, "single")
        if key == self.MODE_IMAGE_TO_VIDEO_START_END:
            return self._start_image_to_video_rows(rows, "start_end")
        if key == self.MODE_CREATE_IMAGE_PROMPT:
            return self._start_generate_image_rows(rows)
        if key == self.MODE_CREATE_IMAGE_REFERENCE:
            return self._start_generate_image_reference_rows(rows)
        if key == self.MODE_CHARACTER_SYNC:
            return self._start_character_sync_rows(rows)

        QMessageBox.warning(
            self,
            "Mode chưa hỗ trợ",
            f"Mode '{self._mode_label(key)}' hiện chưa tích hợp chạy lại tự động.",
        )
        return False

    def _extract_prompt_id_from_log(self, message: str) -> str:
        text = str(message or "")
        m = re.search(r"prompt\s+([A-Za-z0-9_-]+)", text, re.IGNORECASE)
        if not m:
            m = re.search(r"prompt_id\s*[:=]\s*([A-Za-z0-9_-]+)", text, re.IGNORECASE)
        if m:
            return str(m.group(1))
        return ""

    def _set_row_status_detail(self, row: int, code: str, text: str, error_code: str = "", error_message: str = "") -> None:
        item = self.table.item(int(row), self.COL_STATUS)
        if item is None:
            item = QTableWidgetItem("")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(int(row), self.COL_STATUS, item)
        self._set_status_code(row, code)
        try:
            if str(code or "").upper() == "FAILED":
                item.setData(Qt.ItemDataRole.UserRole + 6, str(error_code or "").strip())
                item.setData(Qt.ItemDataRole.UserRole + 7, str(error_message or "").strip())
            else:
                item.setData(Qt.ItemDataRole.UserRole + 6, "")
                item.setData(Qt.ItemDataRole.UserRole + 7, "")
        except Exception:
            pass
        item.setText(str(text or self._status_text(code)))
        self._apply_status_color(row, item.text())
        if not self._loading_status_snapshot:
            self._save_status_snapshot()
            self._update_status_summary()

    def _format_failed_status_text(self, error_code: str = "", error_message: str = "") -> str:
        code = str(error_code or "").strip()
        message = str(error_message or "").strip()
        if code and message:
            return f"Lỗi (mã lỗi: {code} | message: {message})"
        if code:
            return f"Lỗi (mã lỗi: {code})"
        if message:
            return f"Lỗi (message: {message})"
        return "Lỗi"

    def _on_workflow_log(self, message: str) -> None:
        text = str(message or "")

        lower_text = text.lower()
        if "upload ảnh nhân vật thất bại" in lower_text or "không đọc được ảnh" in lower_text:
            self._append_run_log(message)
            failed = self._fail_active_rows_now("CHAR_UPLOAD_FAILED", "Upload ảnh nhân vật thất bại")
            if failed > 0:
                self._append_run_log(
                    f"⚠️ Đã đánh lỗi {failed} dòng do lỗi ảnh nhân vật, worker sẽ xử lý queue tiếp theo."
                )
            return

        pending_queue_rows = 0
        for rr in range(self.table.rowCount()):
            if self._status_code(rr) == "PENDING":
                pending_queue_rows += 1

        if "Hết tất cả prompts" in text:
            if pending_queue_rows > 0:
                self._append_run_log(
                    f"✅ Đã gửi hết prompts của workflow hiện tại, còn {pending_queue_rows} prompt trong hàng chờ."
                )
            else:
                self._append_run_log("✅ Đã gửi hết prompts của workflow hiện tại, tiếp tục chờ video hoàn thành...")
            return

        if "Đã đóng Chrome sau khi gửi hết prompts" in text:
            if pending_queue_rows > 0:
                self._append_run_log(
                    f"🔒 Đã đóng Chrome của workflow hiện tại, còn {pending_queue_rows} prompt trong hàng chờ."
                )
            else:
                self._append_run_log("🔒 Đã đóng Chrome của workflow hiện tại.")
            return

        completion_markers = (
            "Workflow đã hoàn tất",
            "Hết tất cả prompts, chờ video hoàn thành",
            "Tất cả video đã hoàn thành",
            "thoát workflow",
        )
        if any(marker in text for marker in completion_markers):
            return

        self._append_run_log(message)
        prompt_id = self._extract_prompt_id_from_log(text)
        row = self._find_row_by_prompt_id(prompt_id) if prompt_id else -1

        token_markers = (
            "Đang lấy token",
            "lấy token...",
            "Lấy token thành công",
            "Timeout lấy token",
            "Lỗi lấy token",
        )
        if row >= 0 and ("Prompt" in text and ("Đang lấy token" in text or "Lấy token thành công" in text)):
            self._set_row_status_detail(row, "ACTIVE", "Đang tạo")
            return

        if row >= 0 and any(marker in text for marker in token_markers):
            self._set_row_status_detail(row, "TOKEN", "Đang lấy token")
            return

        if row >= 0 and (
            "Bắt đầu gửi request" in text
            or "Đã gửi create video" in text
            or "Gen lại request" in text
            or "Gửi request sync character" in text
        ):
            self._set_row_status_detail(row, "REQUESTED", "Đã gửi request")
            return

        if row >= 0:
            err_match = re.search(r"Lỗi\s*([0-9A-Z_]+)", text)
            if err_match:
                err_code = str(err_match.group(1) or "").strip()
                if err_code:
                    detail_msg = ""
                    msg_match = re.search(r"(?:API\s*lỗi|error|message)\s*[:\-]\s*(.+)", text, re.IGNORECASE)
                    if msg_match:
                        detail_msg = str(msg_match.group(1) or "").strip()
                    self._set_row_status_detail(
                        row,
                        "FAILED",
                        self._format_failed_status_text(err_code, detail_msg),
                        error_code=err_code,
                        error_message=detail_msg,
                    )
                    return

    def _on_video_updated(self, payload: dict) -> None:
        prompt_id = str(payload.get("_prompt_id") or "").strip()
        if not prompt_id:
            prompt_idx = str(payload.get("prompt_idx") or "")
            if "_" in prompt_idx:
                prompt_id = prompt_idx.split("_", 1)[0]
            else:
                prompt_id = prompt_idx
        row = self._find_row_by_prompt_id(prompt_id)
        if row < 0:
            return

        status_code = self._normalize_status_code(str(payload.get("status") or ""))
        if status_code == "PENDING":
            prev_code = self._status_code(row)
            if prev_code in {"TOKEN", "REQUESTED", "ACTIVE"}:
                status_code = "ACTIVE"
        self._set_status_code(row, status_code)
        err_code = str(payload.get("error_code") or "").strip()
        err_message = str(payload.get("error_message") or "").strip()
        if status_code == "FAILED":
            self._set_row_status_detail(
                row,
                "FAILED",
                self._format_failed_status_text(err_code, err_message),
                error_code=err_code,
                error_message=err_message,
            )
        elif status_code == "DOWNLOADING":
            self._set_row_status_detail(row, "DOWNLOADING", "Đang tải video")

        video_path = str(payload.get("video_path") or "").strip()
        image_path = str(payload.get("image_path") or "").strip()
        open_path = video_path or image_path
        preview_path_payload = image_path or open_path
        if open_path:
            path_ok = os.path.isfile(open_path)
            prompt_idx = str(payload.get("prompt_idx") or "")
            output_index = 1
            if "_" in prompt_idx:
                try:
                    output_index = int(prompt_idx.split("_", 1)[1])
                except Exception:
                    output_index = 1
            vid_item = self.table.item(row, self.COL_VIDEO)
            if vid_item is None:
                vid_item = QTableWidgetItem("")
                vid_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, self.COL_VIDEO, vid_item)
            try:
                video_map = dict(vid_item.data(Qt.ItemDataRole.UserRole + 1) or {})
            except Exception:
                video_map = {}
            try:
                preview_map = dict(vid_item.data(Qt.ItemDataRole.UserRole + 4) or {})
            except Exception:
                preview_map = {}
            if path_ok:
                video_map[int(output_index)] = open_path
            if preview_path_payload and os.path.isfile(preview_path_payload):
                preview_map[int(output_index)] = preview_path_payload
            vid_item.setData(Qt.ItemDataRole.UserRole + 1, video_map)
            vid_item.setData(Qt.ItemDataRole.UserRole + 4, preview_map)
            selected_idx = int(vid_item.data(Qt.ItemDataRole.UserRole + 2) or 1)
            if selected_idx not in video_map and video_map:
                selected_idx = sorted(video_map.keys())[0]
                vid_item.setData(Qt.ItemDataRole.UserRole + 2, selected_idx)
            selected_path = str(video_map.get(selected_idx, "") or "")
            selected_preview = str(preview_map.get(selected_idx, "") or selected_path)
            vid_item.setData(Qt.ItemDataRole.UserRole, selected_path)
            vid_item.setText("")

            cell = self.table.cellWidget(row, self.COL_VIDEO)
            if cell is not None:
                self._refresh_video_badges(row)
                self._render_media_preview(row, selected_preview)

            if image_path and os.path.isfile(image_path):
                self._update_character_sync_sheet_preview(row, image_path)

        self._refresh_pending_positions()
        self._try_finalize_grok_batch_now()
        if self._awaiting_completion_confirmation and row in self._active_queue_rows:
            self._try_finish_workflow_completion()

    def _try_finalize_grok_batch_now(self) -> bool:
        rows = sorted(int(r) for r in list(self._active_queue_rows))
        if not rows:
            return False

        grok_rows = [
            r
            for r in rows
            if self._row_mode_key(r) in {self.MODE_GROK_TEXT_TO_VIDEO, self.MODE_GROK_IMAGE_TO_VIDEO}
        ]
        if not grok_rows:
            return False

        for r in grok_rows:
            code = self._status_code(r)
            if code in {"FAILED", "STOPPED", "CANCELED"}:
                continue
            try:
                produced = int(len(self._row_media_map(r)))
            except Exception:
                produced = 0
            if produced >= 1:
                if code not in {"SUCCESSFUL", "FAILED", "STOPPED", "CANCELED"}:
                    self._set_row_status_detail(r, "SUCCESSFUL", "Hoàn thành")
                continue
            return False

        if self._awaiting_completion_confirmation:
            self._try_finish_workflow_completion()
        return True

    def _mark_active_rows_stopped(self) -> None:
        for r in range(self.table.rowCount()):
            code = self._status_code(r)
            if code in {"PENDING", "ACTIVE", "TOKEN", "REQUESTED", "DOWNLOADING"}:
                self._set_row_status_detail(r, "CANCELED", "Hủy")

    def _fail_active_rows_now(self, error_code: str, error_message: str) -> int:
        changed = 0
        for r in sorted(int(x) for x in list(self._active_queue_rows)):
            if r < 0 or r >= self.table.rowCount():
                continue
            if self._is_row_terminal_for_completion(r):
                continue
            self._set_row_status_detail(
                r,
                "FAILED",
                self._format_failed_status_text(error_code, error_message),
                error_code=error_code,
                error_message=error_message,
            )
            changed += 1
        if changed > 0:
            self._refresh_pending_positions()
            if self._awaiting_completion_confirmation:
                self._try_finish_workflow_completion()
        return changed

    def _finalize_unresolved_active_rows_after_exit(self) -> None:
        unresolved_rows: list[int] = []
        for r in sorted(int(x) for x in list(self._active_queue_rows)):
            if r < 0 or r >= self.table.rowCount():
                continue
            if self._is_row_terminal_for_completion(r):
                continue
            unresolved_rows.append(r)

        if not unresolved_rows:
            return

        for r in unresolved_rows:
            try:
                expected = max(1, int(self._row_output_count(r)))
            except Exception:
                expected = 1
            try:
                produced = int(len(self._row_media_map(r)))
            except Exception:
                produced = 0
            msg = self._format_failed_status_text(
                "WORKFLOW_EXITED",
                f"Workflow kết thúc sớm, nhận {produced}/{expected} output",
            )
            self._set_row_status_detail(
                r,
                "FAILED",
                msg,
                error_code="WORKFLOW_EXITED",
                error_message=f"Workflow kết thúc sớm, nhận {produced}/{expected} output",
            )

        self._append_run_log(
            f"⚠️ Workflow đã thoát nhưng còn {len(unresolved_rows)} dòng chưa hoàn tất; đã chuyển sang Lỗi để không kẹt hàng chờ."
        )

    def _on_workflow_complete(self) -> None:
        if self._global_stop_requested:
            self._workflow = None
            self._retry_mode_queue = []
            self._active_queue_rows.clear()
            self._awaiting_completion_confirmation = False
            self._completion_poll_scheduled = False
            self._completion_poll_attempts = 0
            self._close_all_workflow_chrome_profiles_async()
            self._append_run_log("🛑 Đã dừng toàn bộ: không chạy workflow kế tiếp")
            self._refresh_pending_positions()
            self.runStateChanged.emit(False)
            return

        alive_workflows: list[QThread] = []
        for wf in list(self._workflows):
            try:
                if wf and wf.isRunning():
                    alive_workflows.append(wf)
            except Exception:
                pass
        self._workflows = alive_workflows
        self._workflow = self._workflows[-1] if self._workflows else None

        self._refresh_pending_positions()
        if not self._workflows:
            self._finalize_unresolved_active_rows_after_exit()
        self._awaiting_completion_confirmation = True
        self._completion_poll_attempts = 0
        self._try_finish_workflow_completion()

    def _is_row_terminal_for_completion(self, row: int) -> bool:
        try:
            rr = int(row)
        except Exception:
            return True

        if rr < 0 or rr >= self.table.rowCount():
            return True

        code = self._status_code(rr)
        return code in {"SUCCESSFUL", "FAILED", "STOPPED", "CANCELED"}

    def _close_all_workflow_chrome_profiles(self) -> None:
        try:
            from chrome import kill_profile_chrome as kill_veo_chrome, resolve_profile_dir as resolve_veo_profile

            kill_veo_chrome(resolve_veo_profile())
        except Exception:
            pass
        try:
            from grok_chrome_manager import kill_profile_chrome as kill_grok_chrome, resolve_profile_dir as resolve_grok_profile

            kill_grok_chrome(resolve_grok_profile())
        except Exception:
            pass

    def _close_all_workflow_chrome_profiles_async(self) -> None:
        if bool(getattr(self, "_chrome_cleanup_running", False)):
            return
        setattr(self, "_chrome_cleanup_running", True)

        def _run() -> None:
            try:
                self._close_all_workflow_chrome_profiles()
            finally:
                try:
                    setattr(self, "_chrome_cleanup_running", False)
                except Exception:
                    pass

        try:
            threading.Thread(target=_run, daemon=True).start()
        except Exception:
            try:
                setattr(self, "_chrome_cleanup_running", False)
            except Exception:
                pass

    def _schedule_completion_poll(self, delay_ms: int = 500) -> None:
        if self._completion_poll_scheduled:
            return
        self._completion_poll_scheduled = True

        def _poll() -> None:
            self._completion_poll_scheduled = False
            self._try_finish_workflow_completion()

        try:
            QTimer.singleShot(max(100, int(delay_ms)), _poll)
        except Exception:
            self._completion_poll_scheduled = False

    def _try_finish_workflow_completion(self) -> None:
        if not self._awaiting_completion_confirmation:
            return

        rows = sorted(int(r) for r in list(self._active_queue_rows))
        if not rows:
            self._awaiting_completion_confirmation = False
            self.runStateChanged.emit(False)
            return

        all_terminal = True
        for r in rows:
            if not self._is_row_terminal_for_completion(r):
                all_terminal = False
                break

        if all_terminal:
            story_started = self._start_storytelling_export_for_rows(rows)
            self._active_queue_rows.clear()
            self._awaiting_completion_confirmation = False
            self._completion_poll_attempts = 0
            self._completion_poll_scheduled = False
            self._close_all_workflow_chrome_profiles_async()
            if not story_started:
                self.runStateChanged.emit(False)
            return

        self._completion_poll_attempts += 1
        if self._completion_poll_attempts == 1:
            self._append_run_log("⏳ Chưa đủ điều kiện hoàn thành, tiếp tục chờ trạng thái video thực tế...")
        if self._completion_poll_attempts >= 600:
            self._append_run_log("⚠️ Quá thời gian chờ xác nhận hoàn thành, chuyển workflow kế tiếp để tránh kẹt hàng chờ.")
            self._active_queue_rows.clear()
            self._awaiting_completion_confirmation = False
            self._completion_poll_attempts = 0
            self._completion_poll_scheduled = False
            self._close_all_workflow_chrome_profiles_async()
            self.runStateChanged.emit(False)
            return

        self._schedule_completion_poll(500)

    def _start_storytelling_export_for_rows(self, rows: list[int]) -> bool:
        story_rows = [int(r) for r in (rows or []) if self._is_storytelling_row(int(r))]
        if not story_rows:
            return False

        items: list[dict] = []
        skipped = 0
        def story_order(row: int) -> int:
            try:
                return int(self._row_mode_payload(row).get("storytelling_index") or (row + 1))
            except Exception:
                return int(row) + 1

        story_rows.sort(key=story_order)
        for r in story_rows:
            media_map = self._row_media_map(r)
            image_path = str(media_map.get(1) or "").strip()
            if not image_path and media_map:
                try:
                    image_path = str(media_map[sorted(media_map.keys())[0]] or "").strip()
                except Exception:
                    image_path = ""
            if not image_path or not os.path.isfile(image_path):
                skipped += 1
                continue

            payload = self._row_mode_payload(r)
            prompt_item = self.table.item(int(r), self.COL_PROMPT)
            fallback_text = str((prompt_item.text() if prompt_item is not None else "") or "").strip()
            narration = str(payload.get("narration") or "").strip()
            if not narration:
                prompt_obj = self._parse_storytelling_prompt_object(fallback_text)
                narration = str(prompt_obj.get("summary") or "").strip() if isinstance(prompt_obj, dict) else ""
            items.append(
                {
                    "image_path": image_path,
                    "narration": narration,
                    "row": int(r),
                }
            )

        if skipped:
            self._append_run_log(f"⚠️ Bỏ qua {skipped} cảnh Storytelling chưa có ảnh hợp lệ.")
        if not items:
            self._append_run_log("⚠️ Không có ảnh Storytelling thành công để xuất MP4.")
            return False

        output_dir = str(getattr(self._cfg, "video_output_dir", "") or "").strip()
        if not output_dir:
            output_dir = str(Path(DATA_GENERAL_DIR) / "storytelling_exports")

        voice_key = str(getattr(self._cfg, "idea_voice_profile", "None_NoVoice") or "None_NoVoice")
        if voice_key == "None_NoVoice":
            voice_key = str(getattr(self._cfg, "voice_profile", "None_NoVoice") or "None_NoVoice")
        tts_provider = str(getattr(self._cfg, "idea_tts_provider", "auto") or "auto").strip().lower()
        if tts_provider not in {"auto", "edge", "sapi", "off"}:
            tts_provider = "auto"
        if tts_provider == "off":
            voice_key = "None_NoVoice"
        else:
            tts_voice = str(getattr(self._cfg, "idea_tts_voice", "") or "").strip()
            if tts_voice:
                voice_key = tts_voice
        aspect_ratio = str(getattr(self._cfg, "video_aspect_ratio", "9:16") or "9:16")

        self._append_run_log(f"🎞️ Đang xuất MP4 Storytelling từ {len(items)} ảnh...")
        worker = _StorytellingExportWorker(
            items=items,
            output_dir=output_dir,
            voice_key=voice_key,
            tts_provider=tts_provider,
            aspect_ratio=aspect_ratio,
            parent=self,
        )
        worker.log_message.connect(self._append_run_log)
        worker.completed.connect(self._on_storytelling_export_complete)
        self._workflow = worker
        self._workflows.append(worker)
        worker.start()
        self.runStateChanged.emit(True)
        return True

    def _on_storytelling_export_complete(self, result: dict) -> None:
        sender = self.sender()
        alive_workflows: list[QThread] = []
        for wf in list(self._workflows):
            if sender is not None and wf is sender:
                continue
            try:
                if wf and wf.isRunning():
                    alive_workflows.append(wf)
            except Exception:
                pass
        self._workflows = alive_workflows
        self._workflow = self._workflows[-1] if self._workflows else None

        if bool((result or {}).get("success")):
            out_path = str((result or {}).get("path") or "").strip()
            self._append_run_log(f"✅ Đã xuất MP4 Storytelling: {out_path}")
        else:
            self._append_run_log(f"❌ Lỗi xuất MP4 Storytelling: {(result or {}).get('message')}")
        self.runStateChanged.emit(bool(self._workflows))

    def retry_selected_rows(self) -> None:
        rows = self._selected_rows()
        if not rows:
            QMessageBox.warning(self, "Chưa chọn", "Hãy tích chọn các dòng cần tạo lại.")
            return
        self._clear_media_for_rows(rows, delete_files=True)
        self._start_rows_by_mode(rows)

    def _confirm_action(self, title: str, text: str) -> bool:
        return (
            QMessageBox.question(
                self,
                str(title or "Xác nhận"),
                str(text or "Bạn có chắc muốn tiếp tục?"),
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            == QMessageBox.StandardButton.Ok
        )

    def _load_merge_video_module(self):
        module_path = Path(__file__).resolve().parent / "merge+video.py"
        if not module_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file: {module_path}")
        spec = importlib.util.spec_from_file_location("merge_plus_video", str(module_path))
        if spec is None or spec.loader is None:
            raise RuntimeError("Không load được module merge+video.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _video_path_of_row(self, row: int) -> str:
        it = self.table.item(int(row), self.COL_VIDEO)
        if it is None:
            return ""
        try:
            current = str(it.data(Qt.ItemDataRole.UserRole) or "").strip()
        except Exception:
            current = ""
        if current and os.path.isfile(current):
            return current
        try:
            video_map = dict(it.data(Qt.ItemDataRole.UserRole + 1) or {})
        except Exception:
            video_map = {}
        for idx in sorted(video_map.keys()):
            path = str(video_map.get(idx) or "").strip()
            if path and os.path.isfile(path):
                return path
        return ""

    def _collect_checked_video_paths(self) -> list[str]:
        paths: list[str] = []
        for r in self._selected_rows():
            p = self._video_path_of_row(r)
            if p:
                paths.append(p)
        return paths

    def _pick_external_videos(self) -> list[str]:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Chọn video",
            str(getattr(self._cfg, "video_output_dir", str(BASE_DIR)) or str(BASE_DIR)),
            "Video files (*.mp4 *.mkv *.mov *.avi *.flv *.wmv *.webm *.m4v);;All files (*.*)",
        )
        return [str(x) for x in (files or []) if str(x).strip()]

    def _ask_video_source(self, action_name: str) -> list[str]:
        action = str(action_name or "").strip().lower()
        is_cut = "cắt" in action

        title = "Cắt ảnh cuối" if is_cut else "Nối video"
        if is_cut:
            message = "Bạn muốn cắt ảnh từ video đã chọn hay duyệt cắt video khác?"
            btn_selected_text = "Cắt ảnh video đã chọn"
            btn_browse_text = "Duyệt cắt video khác"
        else:
            message = "Bạn muốn nối video đã chọn hay duyệt nối video khác?"
            btn_selected_text = "Nối video đã chọn"
            btn_browse_text = "Duyệt nối video khác"

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(title)
        box.setText(message)
        btn_selected = box.addButton(btn_selected_text, QMessageBox.ButtonRole.AcceptRole)
        btn_browse = box.addButton(btn_browse_text, QMessageBox.ButtonRole.ActionRole)
        btn_cancel = box.addButton("Hủy", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(btn_selected)
        box.exec()

        clicked = box.clickedButton()
        if clicked == btn_cancel or clicked is None:
            return []
        if clicked == btn_selected:
            return self._collect_checked_video_paths()
        if clicked == btn_browse:
            return self._pick_external_videos()
        return []

    def _on_join_video_clicked(self) -> None:
        video_paths = self._ask_video_source("Nối video")
        if len(video_paths) < 2:
            QMessageBox.warning(self, "Thiếu dữ liệu", "Cần ít nhất 2 video để nối.")
            return
        try:
            mod = self._load_merge_video_module()
            base_out = Path(str(getattr(self._cfg, "video_output_dir", str(BASE_DIR)) or str(BASE_DIR)))
            merge_out = base_out / "Video đã nối"
            merged_file = mod.merge_videos(video_paths, str(merge_out), output_stem="video_da_noi")
            self._append_run_log(f"✅ Nối video thành công: {merged_file}")
            QMessageBox.information(self, "Nối video", f"Đã nối video thành công:\n{merged_file}")
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(merge_out)))
        except Exception as exc:
            QMessageBox.critical(self, "Lỗi nối video", str(exc))

    def _on_retry_selected_clicked(self) -> None:
        if not self._confirm_action("Xác nhận", "Bạn có chắc muốn tạo lại video cho các dòng đã chọn?"):
            return
        self.retry_selected_rows()

    def _on_retry_failed_clicked(self) -> None:
        if not self._confirm_action("Xác nhận", "Bạn có chắc muốn tạo lại tất cả video lỗi?"):
            return
        self.retry_failed_rows()

    def _on_cut_last_clicked(self) -> None:
        video_paths = self._ask_video_source("Cắt ảnh cuối")
        if not video_paths:
            QMessageBox.warning(self, "Thiếu dữ liệu", "Không có video để cắt ảnh cuối.")
            return
        try:
            mod = self._load_merge_video_module()
            base_out = Path(str(getattr(self._cfg, "video_output_dir", str(BASE_DIR)) or str(BASE_DIR)))
            frame_out = base_out / "Frame cuối video"
            frames = mod.extract_last_frames(video_paths, str(frame_out))
            self._append_run_log(f"✅ Cắt frame cuối thành công: {len(frames)} ảnh")
            QMessageBox.information(self, "Cắt ảnh cuối", f"Đã cắt {len(frames)} ảnh cuối video.")
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(frame_out)))
        except Exception as exc:
            QMessageBox.critical(self, "Lỗi cắt ảnh cuối", str(exc))

    def retry_failed_rows(self) -> None:
        rows: list[int] = []
        for r in range(self.table.rowCount()):
            if self._status_code(r) == "FAILED":
                rows.append(r)
        if not rows:
            QMessageBox.information(self, "Không có lỗi", "Không có dòng lỗi để tạo lại.")
            return
        self._start_rows_by_mode(rows)

    def _process_pending_copy_video_task(self, task: dict) -> None:
        data = task.get('data', {})
        voice_actor_key = task.get('voice_actor_key', '')
        target_language = task.get('target_language', '')
        source_video_path = task.get('source_video_path', '')
        auto_run = task.get('auto_run', False)

        self._populate_character_sync_from_copy_video(data, source_video_path)
        payload = self.enqueue_copy_video_scenes(
            copy_data=data,
            voice_actor_key=voice_actor_key,
            target_language=target_language,
            source_video_path=source_video_path,
            video_model=video_model,
        )
        if payload and auto_run:
            self._append_run_log('⚡ Tạo ảnh hoàn tất. Tiếp tục đẩy Video Scenes vào hàng chờ.')
            try:
                self.queueJobsRequested.emit([payload])
            except Exception:
                pass
