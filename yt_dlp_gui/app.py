#!/usr/bin/env python3
"""
mme89 yt-dlp GUI Wrapper
This application provides an easy-to-use graphical interface for downloading videos
without using the command line.
"""

# The existing main window keeps its UI layout and event wiring in one module.
# pylint: disable=too-many-lines
import os
import sys
import json
import re
import shutil
import shlex
import subprocess
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit, QTabWidget,
    QGroupBox, QCheckBox, QFileDialog, QMessageBox, QProgressBar, QSizePolicy,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, QProcess, QUrl, QTimer, QRegularExpression, QStandardPaths
from PySide6.QtGui import (
    QFont, QPixmap, QColor, QIcon, QRegularExpressionValidator, QDesktopServices
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from .commands import CommandMixin
from .compatibility import RECOMMENDED_YTDLP_VERSION, is_supported_runtime, needs_ytdlp_update
from .process_utils import hidden_subprocess_kwargs
from .terminal_window import TerminalWindow
from .updates import UpdateChecker
from .version import APP_VERSION
from .workers import DownloadThread, FormatFetcher


APP_ROOT = Path(__file__).resolve().parent.parent


class YtDlpGUI(CommandMixin, QMainWindow):
    """Main window coordinating downloads, settings, and background workers."""
    COLORS = {
        'background': '#f5f5f5',
        'surface': '#ffffff',
        'primary': '#2196F3',
        'primary_dark': '#1976D2',
        'primary_light': '#BBDEFB',

        'text_primary': '#212121',
        'text_secondary': '#757575',
        'text_disabled': '#BDBDBD',

        'success': '#4CAF50',
        'error': '#F44336',
        'warning': '#FF9800',
        'info': '#2196F3',

        'border': '#E0E0E0',
        'border_focus': '#2196F3',
        'hover': '#E3F2FD',
        'pressed': '#BBDEFB',

        'thumbnail_bg': '#EEEEEE',
        'input_bg': '#FFFFFF',
        'button_bg': '#FAFAFA',
        'button_text': '#212121',
    }

    def __init__(self):
        """Initialize application state, build the interface, and schedule update checks."""
        super().__init__()
        self.legacy_config_file = APP_ROOT / "settings.json"
        self.config_file = self.get_config_file_path()
        self.format_fetcher = None
        self.playlist_fetcher = None
        self.download_thread = None
        self.video_formats = []
        self.audio_formats = []
        self.subtitles = {}
        self.automatic_captions = {}
        self.terminal_window = None
        self.ytdlp_version = None
        self.ffmpeg_version = None
        self.js_runtime_version = None
        self.js_runtime_info = None
        self.js_runtime_cache_dirty = True
        self.ytdlp_ejs_status = None
        self.download_queue = []
        self.is_processing_queue = False
        self.current_queue_item = None
        self.format_data = {}
        self.current_playlist_downloads = []
        self.network_manager = QNetworkAccessManager(self)
        self.active_thumbnail_reply = None
        self.is_closing = False
        self.settings_save_timer = None
        self.update_checker = UpdateChecker(APP_VERSION, self)
        self.update_checker.finished.connect(self.on_update_check_finished)
        self.notified_update_versions = set()
        self.update_notification = None

        self.init_ui()
        self.setup_logo()
        self.apply_stylesheet()
        self.load_settings()
        self.setup_settings_autosave()
        self.check_ytdlp_version()
        self.check_ffmpeg_version()
        self.check_js_runtime_version()
        self.check_ytdlp_ejs_status()
        self.update_startup_timer = QTimer(self)
        self.update_startup_timer.setSingleShot(True)
        self.update_startup_timer.timeout.connect(self.check_for_updates)
        self.update_startup_timer.start(1500)
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(7 * 24 * 60 * 60 * 1000)
        self.update_timer.timeout.connect(self.check_for_updates)
        self.update_timer.start()

    def apply_stylesheet(self):
        """Apply consistent stylesheet across all platforms"""
        stylesheet = f"""
            QMainWindow {{
                background-color: {self.COLORS['background']};
            }}

            QWidget {{
                background-color: {self.COLORS['background']};
                color: {self.COLORS['text_primary']};
                font-family: ".AppleSystemUIFont", "Segoe UI", Helvetica, Arial, sans-serif;
                font-size: 13px;
            }}

            QGroupBox {{
                background-color: {self.COLORS['surface']};
                border: 1px solid {self.COLORS['border']};
                border-radius: 6px;
                margin-top: 4px;
                padding-top: 4px;
                font-weight: bold;
                color: {self.COLORS['text_primary']};
            }}

            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 5px;
                background-color: {self.COLORS['surface']};
            }}

            QLineEdit {{
                background-color: {self.COLORS['input_bg']};
                border: 1px solid {self.COLORS['border']};
                border-radius: 4px;
                padding: 6px 8px;
                color: {self.COLORS['text_primary']};
                selection-background-color: {self.COLORS['primary_light']};
            }}

            QLineEdit:focus {{
                border: 2px solid {self.COLORS['border_focus']};
                padding: 5px 7px;
            }}

            QLineEdit:disabled {{
                background-color: {self.COLORS['background']};
                color: {self.COLORS['text_disabled']};
            }}

            QPushButton {{
                background-color: {self.COLORS['button_bg']};
                border: 1px solid {self.COLORS['border']};
                border-radius: 4px;
                padding: 6px 16px;
                color: {self.COLORS['button_text']};
                font-weight: 500;
            }}

            QPushButton:hover {{
                background-color: {self.COLORS['hover']};
                border-color: {self.COLORS['primary']};
            }}

            QPushButton:pressed {{
                background-color: {self.COLORS['pressed']};
            }}

            QPushButton:disabled {{
                background-color: {self.COLORS['background']};
                color: {self.COLORS['text_disabled']};
                border-color: {self.COLORS['border']};
            }}

            QComboBox {{
                background-color: {self.COLORS['input_bg']};
                border: 1px solid {self.COLORS['border']};
                border-radius: 4px;
                color: {self.COLORS['text_primary']};
            }}

            QComboBox:focus {{
                border: 2px solid {self.COLORS['border_focus']};
            }}

            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}

            QComboBox QAbstractItemView {{
                background-color: {self.COLORS['surface']};
                border: 1px solid {self.COLORS['border']};
                selection-background-color: {self.COLORS['primary_light']};
                selection-color: {self.COLORS['text_primary']};
                outline: none;
            }}

            QTextEdit {{
                background-color: {self.COLORS['surface']};
                border: 1px solid {self.COLORS['border']};
                border-radius: 4px;
                padding: 8px;
                color: {self.COLORS['text_primary']};
                selection-background-color: {self.COLORS['primary_light']};
            }}

            QTableWidget {{
                background-color: {self.COLORS['surface']};
                border: 1px solid {self.COLORS['border']};
                border-radius: 4px;
                gridline-color: {self.COLORS['border']};
                color: {self.COLORS['text_primary']};
            }}

            QTableWidget::item {{
                padding: 4px;
            }}

            QTableWidget::item:selected {{
                background-color: {self.COLORS['primary_light']};
                color: {self.COLORS['text_primary']};
            }}

            QHeaderView::section {{
                background-color: {self.COLORS['button_bg']};
                border: none;
                border-right: 1px solid {self.COLORS['border']};
                border-bottom: 1px solid {self.COLORS['border']};
                padding: 6px;
                font-weight: bold;
                color: {self.COLORS['text_primary']};
            }}

            QTabWidget::pane {{
                border: 1px solid {self.COLORS['border']};
                border-radius: 4px;
                background-color: {self.COLORS['surface']};
                top: -1px;
            }}

            QTabBar::tab {{
                background-color: {self.COLORS['button_bg']};
                border: 1px solid {self.COLORS['border']};
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 8px 16px;
                margin-right: 2px;
                color: {self.COLORS['text_secondary']};
            }}

            QTabBar::tab:selected {{
                background-color: {self.COLORS['surface']};
                color: {self.COLORS['primary']};
                font-weight: bold;
            }}

            QTabBar::tab:hover {{
                background-color: {self.COLORS['hover']};
            }}

            QProgressBar {{
                border: 1px solid {self.COLORS['border']};
                border-radius: 4px;
                text-align: center;
                background-color: {self.COLORS['background']};
                color: {self.COLORS['text_primary']};
            }}

            QProgressBar::chunk {{
                background-color: {self.COLORS['primary']};
                border-radius: 3px;
            }}

            QCheckBox {{
                color: {self.COLORS['text_primary']};
                spacing: 6px;
            }}

            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 1px solid {self.COLORS['border']};
                border-radius: 3px;
                background-color: {self.COLORS['input_bg']};
            }}

            QCheckBox::indicator:checked {{
                background-color: {self.COLORS['primary']};
                border-color: {self.COLORS['primary']};
            }}

            QLabel {{
                color: {self.COLORS['text_primary']};
                background-color: transparent;
            }}

            QStatusBar {{
                background-color: {self.COLORS['surface']};
                border-top: 1px solid {self.COLORS['border']};
                color: {self.COLORS['text_secondary']};
            }}

            QScrollBar:vertical {{
                border: none;
                background-color: {self.COLORS['background']};
                width: 12px;
                margin: 0;
            }}

            QScrollBar::handle:vertical {{
                background-color: {self.COLORS['text_disabled']};
                border-radius: 6px;
                min-height: 20px;
            }}

            QScrollBar::handle:vertical:hover {{
                background-color: {self.COLORS['text_secondary']};
            }}

            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}

            QScrollBar:horizontal {{
                border: none;
                background-color: {self.COLORS['background']};
                height: 12px;
                margin: 0;
            }}

            QScrollBar::handle:horizontal {{
                background-color: {self.COLORS['text_disabled']};
                border-radius: 6px;
                min-width: 20px;
            }}

            QScrollBar::handle:horizontal:hover {{
                background-color: {self.COLORS['text_secondary']};
            }}

            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
        """
        self.setStyleSheet(stylesheet)

    def setup_logo(self):
        """Setup window icon and logo display"""
        logo_path = APP_ROOT / "assets" / "logo.png"
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))

            logo_pixmap = QPixmap(str(logo_path))
            self.about_logo_label.setPixmap(logo_pixmap.scaled(
                128, 128,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))

    def init_ui(self):
        """Build the main window, URL controls, and feature tabs."""
        self.setWindowTitle(f"mme89 yt-dlp GUI - v{APP_VERSION}")
        self.setFixedSize(1200, 900)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        url_group = QGroupBox("YouTube URL")
        url_group.setFixedHeight(280)
        url_main_layout = QVBoxLayout()

        url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.youtube.com/watch?v=...")
        self.analyze_btn = QPushButton("Analyze")
        self.analyze_btn.clicked.connect(self.fetch_formats)
        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.analyze_btn)
        url_main_layout.addLayout(url_layout)

        thumbnail_info_layout = QHBoxLayout()

        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(320, 180)
        self.thumbnail_label.setScaledContents(True)
        self.thumbnail_label.setStyleSheet(
            f"border: 1px solid {self.COLORS['border']}; "
            f"background-color: {self.COLORS['thumbnail_bg']};"
        )
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setText("Thumbnail will appear here")
        thumbnail_info_layout.addWidget(self.thumbnail_label)

        info_widget = QWidget()
        info_widget.setFixedHeight(180)
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        self.title_label = QLabel("Title: -")
        self.title_label.setWordWrap(True)
        self.duration_label = QLabel("Duration: -")
        self.uploader_label = QLabel("Uploader: -")
        self.upload_date_label = QLabel("Uploaded: -")
        self.views_label = QLabel("Views: -")
        self.likes_label = QLabel("Likes: -")
        info_layout.addWidget(self.title_label)
        info_layout.addWidget(self.duration_label)
        info_layout.addWidget(self.uploader_label)
        info_layout.addWidget(self.upload_date_label)
        info_layout.addWidget(self.views_label)
        info_layout.addWidget(self.likes_label)
        info_layout.addStretch()
        thumbnail_info_layout.addWidget(info_widget)

        url_main_layout.addLayout(thumbnail_info_layout)
        url_group.setLayout(url_main_layout)
        main_layout.addWidget(url_group)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.create_download_tab()

        self.create_queue_tab()

        self.create_playlist_tab()

        self.create_advanced_tab()

        self.create_options_tab()

        self.create_about_tab()

        self.statusBar().showMessage("Ready")

    def create_download_tab(self):
        """Build format selection, subtitle controls, and download actions."""
        download_widget = QWidget()
        layout = QVBoxLayout(download_widget)

        video_group = QGroupBox("Video Format")
        video_layout = QVBoxLayout()
        self.video_combo = QComboBox()
        self.video_combo.addItem("Fetch formats first...", "")
        video_layout.addWidget(self.video_combo)
        video_group.setLayout(video_layout)
        layout.addWidget(video_group)

        audio_group = QGroupBox("Audio Format")
        audio_layout = QVBoxLayout()
        self.audio_combo = QComboBox()
        self.audio_combo.addItem("Fetch formats first...", "")
        audio_layout.addWidget(self.audio_combo)
        audio_group.setLayout(audio_layout)
        layout.addWidget(audio_group)

        subtitle_group = QGroupBox("Subtitles")
        subtitle_layout = QVBoxLayout()
        subtitle_row_layout = QHBoxLayout()
        self.subtitle_combo = QComboBox()
        self.subtitle_combo.addItem("None", "")
        self.subtitle_combo.addItem("English", "en")
        self.subtitle_combo.addItem("All subtitles", "all")
        self.subtitle_combo.currentIndexChanged.connect(self.update_subtitle_option_states)
        subtitle_row_layout.addWidget(self.subtitle_combo, 1)

        self.include_live_chat_checkbox = QCheckBox("Include live chat")
        self.include_live_chat_checkbox.setEnabled(False)
        subtitle_row_layout.addWidget(self.include_live_chat_checkbox)

        self.keep_subtitle_files_checkbox = QCheckBox("Keep subtitle files")
        self.keep_subtitle_files_checkbox.setEnabled(False)
        subtitle_row_layout.addWidget(self.keep_subtitle_files_checkbox)

        subtitle_layout.addLayout(subtitle_row_layout)

        subtitle_help = QLabel(
            'By default, subtitles are embedded into the downloaded media. '
            'Enable "Keep subtitle files" to also save separate subtitle files.'
        )
        subtitle_help.setWordWrap(True)
        subtitle_help.setStyleSheet(f"color: {self.COLORS['text_secondary']}; font-size: 10pt;")
        subtitle_layout.addWidget(subtitle_help)

        subtitle_group.setLayout(subtitle_layout)
        layout.addWidget(subtitle_group)

        manual_group = QGroupBox("Or enter format manually (overrides dropdowns)")
        manual_layout = QVBoxLayout()
        self.format_input = QLineEdit()
        self.format_input.setPlaceholderText("e.g., 137+140 or leave empty")
        manual_layout.addWidget(self.format_input)
        manual_group.setLayout(manual_layout)
        layout.addWidget(manual_group)

        download_btn_layout = QHBoxLayout()
        self.download_btn = QPushButton("Download Now")
        self.download_btn.clicked.connect(self.download_video)
        self.add_to_queue_btn = QPushButton("Add to Queue")
        self.add_to_queue_btn.clicked.connect(self.add_to_queue)
        download_btn_layout.addWidget(self.download_btn)
        download_btn_layout.addWidget(self.add_to_queue_btn)
        layout.addLayout(download_btn_layout)

        self.download_page_status_label = QLabel("Enter a URL and click Analyze")
        self.download_page_status_label.setMinimumHeight(24)
        self.download_page_status_label.setStyleSheet(f"color: {self.COLORS['text_secondary']};")
        layout.addWidget(self.download_page_status_label)

        progress_group = QGroupBox("Download Progress")
        progress_layout = QVBoxLayout()
        progress_layout.setContentsMargins(12, 18, 12, 12)
        progress_layout.setSpacing(8)
        progress_group.setFixedHeight(115)
        progress_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(20)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        progress_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        self.abort_btn = QPushButton("Abort Download")
        self.abort_btn.clicked.connect(self.abort_download)
        self.abort_btn.setEnabled(False)
        self.abort_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.COLORS['error']};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: #D32F2F;
            }}
            QPushButton:pressed {{
                background-color: #C62828;
            }}
            QPushButton:disabled {{
                background-color: {self.COLORS['text_disabled']};
            }}
        """)
        self.abort_btn.setMinimumWidth(self.abort_btn.sizeHint().width() + 20)
        self.abort_btn.setFixedHeight(34)
        self.abort_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        progress_status_layout = QHBoxLayout()
        progress_status_layout.setContentsMargins(0, 0, 0, 0)
        progress_status_layout.setSpacing(12)
        progress_status_layout.addWidget(self.status_label, 1)
        progress_status_layout.addWidget(self.abort_btn)
        progress_layout.addLayout(progress_status_layout)

        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        layout.addStretch()

        self.tabs.addTab(download_widget, "Download")

    def create_playlist_tab(self):
        """Build playlist loading and selective download controls."""
        playlist_widget = QWidget()
        layout = QVBoxLayout(playlist_widget)

        btn_layout = QHBoxLayout()
        self.list_playlist_btn = QPushButton("Load Playlist")
        self.list_playlist_btn.clicked.connect(self.load_playlist_items)
        self.download_playlist_btn = QPushButton("Download Checked")
        self.download_playlist_btn.clicked.connect(self.download_playlist)
        self.download_playlist_btn.setEnabled(False)
        self.check_all_playlist_btn = QPushButton("Check All")
        self.check_all_playlist_btn.clicked.connect(self.check_all_playlist)
        self.check_all_playlist_btn.setEnabled(False)
        self.uncheck_all_playlist_btn = QPushButton("Uncheck All")
        self.uncheck_all_playlist_btn.clicked.connect(self.uncheck_all_playlist)
        self.uncheck_all_playlist_btn.setEnabled(False)
        btn_layout.addWidget(self.list_playlist_btn)
        btn_layout.addWidget(self.download_playlist_btn)
        btn_layout.addWidget(self.check_all_playlist_btn)
        btn_layout.addWidget(self.uncheck_all_playlist_btn)
        btn_layout.addStretch()

        quality_label = QLabel("Quality:")
        btn_layout.addWidget(quality_label)
        self.playlist_quality_combo = QComboBox()
        self.playlist_quality_combo.addItem("Best", "best")
        self.playlist_quality_combo.addItem("2160p (4K)", "2160")
        self.playlist_quality_combo.addItem("1440p (2K)", "1440")
        self.playlist_quality_combo.addItem("1080p (Full HD)", "1080")
        self.playlist_quality_combo.addItem("720p (HD)", "720")
        self.playlist_quality_combo.addItem("480p", "480")
        self.playlist_quality_combo.addItem("360p", "360")
        self.playlist_quality_combo.setCurrentIndex(3)
        btn_layout.addWidget(self.playlist_quality_combo)

        layout.addLayout(btn_layout)

        self.playlist_table = QTableWidget()
        self.playlist_table.setColumnCount(5)
        self.playlist_table.setHorizontalHeaderLabels(
            ["", "Status", "Title", "Duration", "Uploader"]
        )
        self.playlist_table.setColumnWidth(0, 30)
        self.playlist_table.setColumnWidth(1, 100)
        self.playlist_table.setColumnWidth(3, 80)
        self.playlist_table.setColumnWidth(4, 250)
        self.playlist_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.playlist_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.playlist_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.playlist_table)

        self.playlist_status_label = QLabel("Enter a playlist URL and click 'Load Playlist'")
        self.playlist_status_label.setStyleSheet(f"color: {self.COLORS['text_secondary']};")
        layout.addWidget(self.playlist_status_label)

        self.tabs.addTab(playlist_widget, "Playlist")

    def create_queue_tab(self):
        """Build the download queue table and processing controls."""
        queue_widget = QWidget()
        layout = QVBoxLayout(queue_widget)

        btn_layout = QHBoxLayout()
        self.start_queue_btn = QPushButton("Start Queue")
        self.start_queue_btn.clicked.connect(self.start_queue_processing)
        self.start_queue_btn.setEnabled(False)
        self.stop_queue_btn = QPushButton("Stop Queue")
        self.stop_queue_btn.clicked.connect(self.stop_queue_processing)
        self.stop_queue_btn.setEnabled(False)
        self.clear_queue_btn = QPushButton("Clear Queue")
        self.clear_queue_btn.clicked.connect(self.clear_queue)
        self.remove_selected_btn = QPushButton("Remove Selected")
        self.remove_selected_btn.clicked.connect(self.remove_selected_from_queue)
        btn_layout.addWidget(self.start_queue_btn)
        btn_layout.addWidget(self.stop_queue_btn)
        btn_layout.addWidget(self.remove_selected_btn)
        btn_layout.addWidget(self.clear_queue_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.queue_table = QTableWidget()
        self.queue_table.setColumnCount(6)
        self.queue_table.setHorizontalHeaderLabels(
            ["#", "Status", "URL", "Title", "Format", "Size"]
        )
        self.queue_table.setColumnWidth(0, 40)
        self.queue_table.setColumnWidth(1, 100)
        self.queue_table.setColumnWidth(4, 100)
        self.queue_table.setColumnWidth(5, 80)
        self.queue_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.queue_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.queue_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.queue_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.queue_table.verticalHeader().setVisible(False)
        layout.addWidget(self.queue_table)

        self.queue_status_label = QLabel("Queue is empty. Add videos from the Download tab.")
        self.queue_status_label.setStyleSheet(f"color: {self.COLORS['text_secondary']};")
        layout.addWidget(self.queue_status_label)

        self.tabs.addTab(queue_widget, "Queue")

    def create_advanced_tab(self):
        """Build custom command and metadata inspection controls."""
        advanced_widget = QWidget()
        layout = QVBoxLayout(advanced_widget)

        custom_group = QGroupBox("Custom yt-dlp arguments")
        custom_layout = QVBoxLayout()
        self.custom_input = QLineEdit()
        self.custom_input.setPlaceholderText(
            "Arguments only; URL comes from the YouTube URL field"
        )
        self.custom_input.setToolTip(
            "Enter yt-dlp options only. The URL is appended automatically."
        )
        custom_layout.addWidget(self.custom_input)
        custom_group.setLayout(custom_layout)
        layout.addWidget(custom_group)

        btn_layout = QHBoxLayout()
        self.execute_custom_btn = QPushButton("Execute Custom")
        self.execute_custom_btn.clicked.connect(self.execute_custom)
        self.metadata_btn = QPushButton("Get Metadata")
        self.metadata_btn.clicked.connect(self.get_metadata)
        self.list_subs_btn = QPushButton("List Subtitles")
        self.list_subs_btn.clicked.connect(self.list_subtitles)
        btn_layout.addWidget(self.execute_custom_btn)
        btn_layout.addWidget(self.metadata_btn)
        btn_layout.addWidget(self.list_subs_btn)
        layout.addLayout(btn_layout)

        self.advanced_output = QTextEdit()
        self.advanced_output.setReadOnly(True)
        self.advanced_output.setFont(QFont("Menlo", 10))
        layout.addWidget(self.advanced_output)

        self.tabs.addTab(advanced_widget, "Advanced")

    def create_options_tab(self):
        """Build settings for tool paths, download rates, and output preferences."""
        options_widget = QWidget()
        layout = QVBoxLayout(options_widget)
        layout.setSpacing(0)

        custom_opts_label = QLabel("Custom yt-dlp options (applied to all operations):")
        layout.addWidget(custom_opts_label)
        layout.addSpacing(3)
        self.custom_options_input = QLineEdit()
        self.custom_options_input.setMinimumHeight(20)
        self.custom_options_input.setPlaceholderText("e.g., --cookies /path/to/cookies.txt")
        layout.addWidget(self.custom_options_input)

        layout.addSpacing(10)

        dest_label = QLabel("Download destination (leave empty for system Downloads folder):")
        layout.addWidget(dest_label)
        layout.addSpacing(3)
        dest_input_layout = QHBoxLayout()
        dest_input_layout.setContentsMargins(0, 0, 0, 0)
        dest_input_layout.setSpacing(6)
        self.destination_input = QLineEdit()
        self.destination_input.setMinimumHeight(20)
        self.destination_input.setPlaceholderText("System Downloads folder or /path/to/folder")
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.browse_destination)
        dest_input_layout.addWidget(self.destination_input)
        dest_input_layout.addWidget(self.browse_btn)
        layout.addLayout(dest_input_layout)

        layout.addSpacing(10)

        paths_group = QGroupBox("Binary Paths")
        paths_group_layout = QVBoxLayout()
        paths_group_layout.setSpacing(0)
        paths_group_layout.setContentsMargins(10, 10, 10, 2)

        paths_layout = QHBoxLayout()
        paths_layout.setSpacing(6)
        paths_layout.setContentsMargins(0, 0, 0, 0)

        ytdlp_layout = QVBoxLayout()
        ytdlp_layout.setSpacing(0)
        ytdlp_path_label = QLabel("yt-dlp path:")
        ytdlp_layout.addWidget(ytdlp_path_label)
        ytdlp_layout.addSpacing(3)
        ytdlp_path_input_layout = QHBoxLayout()
        ytdlp_path_input_layout.setContentsMargins(0, 0, 0, 0)
        ytdlp_path_input_layout.setSpacing(6)
        self.ytdlp_path_input = QLineEdit()
        self.ytdlp_path_input.setMinimumHeight(20)
        self.ytdlp_path_input.setMaximumWidth(400)
        self.ytdlp_path_input.setPlaceholderText("/usr/local/bin/yt-dlp")
        self.browse_ytdlp_btn = QPushButton("Browse...")
        self.browse_ytdlp_btn.clicked.connect(self.browse_ytdlp_path)
        ytdlp_path_input_layout.addWidget(self.ytdlp_path_input)
        ytdlp_path_input_layout.addWidget(self.browse_ytdlp_btn)
        ytdlp_layout.addLayout(ytdlp_path_input_layout)
        paths_layout.addLayout(ytdlp_layout)

        ffmpeg_layout = QVBoxLayout()
        ffmpeg_layout.setSpacing(0)
        ffmpeg_label = QLabel("FFmpeg path:")
        ffmpeg_layout.addWidget(ffmpeg_label)
        ffmpeg_layout.addSpacing(3)
        ffmpeg_path_input_layout = QHBoxLayout()
        ffmpeg_path_input_layout.setContentsMargins(0, 0, 0, 0)
        ffmpeg_path_input_layout.setSpacing(6)
        self.ffmpeg_path_input = QLineEdit()
        self.ffmpeg_path_input.setMinimumHeight(20)
        self.ffmpeg_path_input.setMaximumWidth(400)
        self.ffmpeg_path_input.setPlaceholderText("/usr/local/bin/ffmpeg")
        self.browse_ffmpeg_btn = QPushButton("Browse...")
        self.browse_ffmpeg_btn.clicked.connect(self.browse_ffmpeg_path)
        ffmpeg_path_input_layout.addWidget(self.ffmpeg_path_input)
        ffmpeg_path_input_layout.addWidget(self.browse_ffmpeg_btn)
        ffmpeg_layout.addLayout(ffmpeg_path_input_layout)
        paths_layout.addLayout(ffmpeg_layout)

        paths_group_layout.addLayout(paths_layout)

        path_help = QLabel("Leave empty for system default")
        path_help.setStyleSheet(f"color: {self.COLORS['text_secondary']}; font-size: 10pt;")
        paths_group_layout.addWidget(path_help)

        paths_group.setLayout(paths_group_layout)
        layout.addWidget(paths_group)

        layout.addSpacing(10)

        rates_group = QGroupBox("Download Rate Limits")
        rates_group_layout = QVBoxLayout()
        rates_group_layout.setSpacing(0)
        rates_group_layout.setContentsMargins(10, 10, 10, 2)

        rates_layout = QHBoxLayout()
        rates_layout.setSpacing(6)
        rates_layout.setContentsMargins(0, 0, 0, 0)
        rate_validator = QRegularExpressionValidator(
            QRegularExpression(r"^\d+(?:\.\d+)?[KMGkmg]?$"),
            self,
        )

        max_rate_layout = QVBoxLayout()
        max_rate_layout.setSpacing(0)
        limit_rate_label = QLabel("Maximum download rate:")
        max_rate_layout.addWidget(limit_rate_label)
        max_rate_layout.addSpacing(3)
        self.limit_rate_input = QLineEdit()
        self.limit_rate_input.setMinimumHeight(20)
        self.limit_rate_input.setMaximumWidth(160)
        self.limit_rate_input.setPlaceholderText("e.g., 50K, 4.2M, 1G")
        self.limit_rate_input.setValidator(rate_validator)
        max_rate_layout.addWidget(self.limit_rate_input)
        rates_layout.addLayout(max_rate_layout)

        rates_layout.addSpacing(20)

        min_rate_layout = QVBoxLayout()
        min_rate_layout.setSpacing(0)
        throttled_rate_label = QLabel("Minimum download rate:")
        min_rate_layout.addWidget(throttled_rate_label)
        min_rate_layout.addSpacing(3)
        self.throttled_rate_input = QLineEdit()
        self.throttled_rate_input.setMinimumHeight(20)
        self.throttled_rate_input.setMaximumWidth(160)
        self.throttled_rate_input.setPlaceholderText("e.g., 100K, 1M")
        self.throttled_rate_input.setValidator(rate_validator)
        min_rate_layout.addWidget(self.throttled_rate_input)
        rates_layout.addLayout(min_rate_layout)

        rates_layout.addStretch()

        rates_group_layout.addLayout(rates_layout)
        rates_group_layout.addSpacing(1)

        rate_help = QLabel("Leave empty for unlimited. K=kilobytes/s, M=megabytes/s, G=gigabytes/s")
        rate_help.setStyleSheet(f"color: {self.COLORS['text_secondary']}; font-size: 10pt;")
        rates_group_layout.addWidget(rate_help)

        rates_group.setLayout(rates_group_layout)
        layout.addWidget(rates_group)

        layout.addSpacing(10)

        self.show_terminal_checkbox = QCheckBox("Show detailed terminal output in separate window")
        self.show_terminal_checkbox.stateChanged.connect(self.toggle_terminal_output)
        layout.addWidget(self.show_terminal_checkbox)

        layout.addSpacing(5)

        self.show_auto_captions_checkbox = QCheckBox(
            "Show auto-generated captions in subtitle dropdown"
        )
        self.show_auto_captions_checkbox.stateChanged.connect(
            self.on_show_auto_captions_changed
        )
        layout.addWidget(self.show_auto_captions_checkbox)

        layout.addSpacing(10)

        self.save_settings_btn = QPushButton("Save Settings")
        self.save_settings_btn.clicked.connect(
            lambda checked=False: self.save_settings(show_feedback=True)
        )
        layout.addWidget(self.save_settings_btn)

        layout.addStretch()

        info_label = QLabel(f"Settings auto-saved to: {self.config_file}")
        info_label.setWordWrap(True)
        info_label.setStyleSheet(f"color: {self.COLORS['text_secondary']};")
        layout.addWidget(info_label)

        self.tabs.addTab(options_widget, "Options")

    def configure_about_status_label(self, label):
        """Allow dependency status text to wrap inside its About column."""
        label.setWordWrap(True)
        label.setMinimumWidth(0)
        label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def create_about_tab(self):
        """Show application details, update controls, and dependency status."""
        about_widget = QWidget()
        layout = QVBoxLayout(about_widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        header_layout = QHBoxLayout()
        header_layout.addStretch()

        self.about_logo_label = QLabel()
        self.about_logo_label.setFixedSize(128, 128)
        self.about_logo_label.setScaledContents(True)
        self.about_logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.about_logo_label)

        header_layout.addSpacing(20)

        version_widget = QWidget()
        version_layout = QVBoxLayout(version_widget)
        version_layout.setContentsMargins(0, 0, 0, 0)
        version_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        app_title = QLabel("mme89 yt-dlp GUI")
        app_title_font = QFont()
        app_title_font.setPointSize(16)
        app_title_font.setBold(True)
        app_title.setFont(app_title_font)
        version_layout.addWidget(app_title)

        version_label = QLabel(f"Version {APP_VERSION}")
        version_label.setStyleSheet(f"color: {self.COLORS['text_secondary']};")
        version_layout.addWidget(version_label)

        self.update_status_label = QLabel("Updates are checked automatically.")
        self.update_status_label.setWordWrap(True)
        self.update_status_label.setTextFormat(Qt.TextFormat.RichText)
        self.update_status_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        self.update_status_label.setOpenExternalLinks(True)
        version_layout.addWidget(self.update_status_label)
        self.check_updates_button = QPushButton("Check for Updates")
        self.check_updates_button.clicked.connect(self.check_for_updates)
        version_layout.addWidget(self.check_updates_button)

        header_layout.addWidget(version_widget)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        layout.addSpacing(20)

        desc_label = QLabel(
            "A graphical interface for yt-dlp with format selection, "
            "playlist support, and download queue management."
        )
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc_label)

        layout.addSpacing(5)

        github_label = QLabel(
            'GitHub: <a href="https://github.com/mme89/yt-dlp-gui">github.com/mme89/yt-dlp-gui</a>'
        )
        github_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        github_label.setTextFormat(Qt.TextFormat.RichText)
        github_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        github_label.setOpenExternalLinks(True)
        github_label.setStyleSheet(f"color: {self.COLORS['text_secondary']};")
        layout.addWidget(github_label)

        layout.addSpacing(5)

        license_info = QLabel(
            'Licensed under GNU GPL v3+ - '
            '<a href="https://github.com/mme89/yt-dlp-gui/blob/main/LICENSE">View License</a>'
        )
        license_info.setWordWrap(True)
        license_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        license_info.setTextFormat(Qt.TextFormat.RichText)
        license_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        license_info.setOpenExternalLinks(True)
        license_info.setStyleSheet(f"color: {self.COLORS['text_secondary']}; font-size: 10pt;")
        layout.addWidget(license_info)

        layout.addSpacing(20)

        powered_by_container = QWidget()
        powered_by_container.setMinimumWidth(1000)
        powered_by_container.setMaximumWidth(1080)
        powered_by_container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        powered_by_layout = QHBoxLayout(powered_by_container)
        powered_by_layout.setContentsMargins(0, 0, 0, 0)
        powered_by_layout.setSpacing(48)

        ytdlp_widget = QWidget()
        ytdlp_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        ytdlp_layout = QVBoxLayout(ytdlp_widget)
        ytdlp_layout.setContentsMargins(0, 0, 0, 0)

        ytdlp_label = QLabel("yt-dlp")
        ytdlp_font = QFont()
        ytdlp_font.setPointSize(14)
        ytdlp_font.setBold(True)
        ytdlp_label.setFont(ytdlp_font)
        ytdlp_layout.addWidget(ytdlp_label)

        self.ytdlp_version_label = QLabel("Checking version...")
        self.configure_about_status_label(self.ytdlp_version_label)
        self.ytdlp_version_label.setStyleSheet(
            f"color: {self.COLORS['text_secondary']}; font-style: italic;"
        )
        ytdlp_layout.addWidget(self.ytdlp_version_label)

        ytdlp_layout.addSpacing(10)

        ytdlp_info = QLabel(
            'Core download engine.<br>'
            'Feature-rich command-line<br>'
            'audio/video downloader.<br><br>'
            f'Recommended: yt-dlp {RECOMMENDED_YTDLP_VERSION} or newer.<br>'
            'Python installs require Python 3.11+.<br>'
            'Windows binaries require Windows 10+.<br><br>'
            'GitHub: <a href="https://github.com/yt-dlp/yt-dlp">yt-dlp/yt-dlp</a>'
        )
        ytdlp_info.setWordWrap(True)
        ytdlp_info.setTextFormat(Qt.TextFormat.RichText)
        ytdlp_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        ytdlp_info.setOpenExternalLinks(True)
        ytdlp_layout.addWidget(ytdlp_info)
        ytdlp_layout.addStretch()

        powered_by_layout.addWidget(ytdlp_widget, 1)

        js_runtime_widget = QWidget()
        js_runtime_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        js_runtime_layout = QVBoxLayout(js_runtime_widget)
        js_runtime_layout.setContentsMargins(0, 0, 0, 0)

        js_runtime_label = QLabel("JS Runtime")
        js_runtime_font = QFont()
        js_runtime_font.setPointSize(14)
        js_runtime_font.setBold(True)
        js_runtime_label.setFont(js_runtime_font)
        js_runtime_layout.addWidget(js_runtime_label)

        self.js_runtime_version_label = QLabel("Checking runtime...")
        self.configure_about_status_label(self.js_runtime_version_label)
        self.js_runtime_version_label.setStyleSheet(
            f"color: {self.COLORS['text_secondary']}; font-style: italic;"
        )
        js_runtime_layout.addWidget(self.js_runtime_version_label)

        js_runtime_layout.addSpacing(10)

        js_runtime_info = QLabel(
            'Used by yt-dlp for YouTube<br>'
            'JavaScript extraction.<br><br>'
            'Recommended: Deno 2.3+ or Node.js 22+.<br>'
            'QuickJS is also supported.<br>'
            'Bun is deprecated (1.2.11–1.3.14 only).<br><br>'
            'Docs: <a href="https://github.com/yt-dlp/yt-dlp/wiki/EJS">yt-dlp EJS wiki</a>'
        )
        js_runtime_info.setWordWrap(True)
        js_runtime_info.setTextFormat(Qt.TextFormat.RichText)
        js_runtime_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        js_runtime_info.setOpenExternalLinks(True)
        js_runtime_layout.addWidget(js_runtime_info)
        js_runtime_layout.addStretch()

        powered_by_layout.addWidget(js_runtime_widget, 1)

        ytdlp_ejs_widget = QWidget()
        ytdlp_ejs_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        ytdlp_ejs_layout = QVBoxLayout(ytdlp_ejs_widget)
        ytdlp_ejs_layout.setContentsMargins(0, 0, 0, 0)

        ytdlp_ejs_label = QLabel("yt-dlp-ejs")
        ytdlp_ejs_font = QFont()
        ytdlp_ejs_font.setPointSize(14)
        ytdlp_ejs_font.setBold(True)
        ytdlp_ejs_label.setFont(ytdlp_ejs_font)
        ytdlp_ejs_layout.addWidget(ytdlp_ejs_label)

        self.ytdlp_ejs_status_label = QLabel("Checking package...")
        self.configure_about_status_label(self.ytdlp_ejs_status_label)
        self.ytdlp_ejs_status_label.setStyleSheet(
            f"color: {self.COLORS['text_secondary']}; font-style: italic;"
        )
        ytdlp_ejs_layout.addWidget(self.ytdlp_ejs_status_label)

        ytdlp_ejs_layout.addSpacing(10)

        ytdlp_ejs_info = QLabel(
            'Required by yt-dlp for full YouTube support.<br><br>'
            'Included in official yt-dlp binaries.<br>'
            'For pip installs, use:<br>'
            '<code>pip install -U &quot;yt-dlp[default]&quot;</code><br>'
            'Run this in the environment containing yt-dlp.<br><br>'
            'Package: <a href="https://github.com/yt-dlp/ejs">yt-dlp/ejs</a>'
        )
        ytdlp_ejs_info.setWordWrap(True)
        ytdlp_ejs_info.setTextFormat(Qt.TextFormat.RichText)
        ytdlp_ejs_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        ytdlp_ejs_info.setOpenExternalLinks(True)
        ytdlp_ejs_layout.addWidget(ytdlp_ejs_info)
        ytdlp_ejs_layout.addStretch()

        powered_by_layout.addWidget(ytdlp_ejs_widget, 1)

        ffmpeg_widget = QWidget()
        ffmpeg_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        ffmpeg_layout = QVBoxLayout(ffmpeg_widget)
        ffmpeg_layout.setContentsMargins(0, 0, 0, 0)

        ffmpeg_label = QLabel("FFmpeg")
        ffmpeg_font = QFont()
        ffmpeg_font.setPointSize(14)
        ffmpeg_font.setBold(True)
        ffmpeg_label.setFont(ffmpeg_font)
        ffmpeg_layout.addWidget(ffmpeg_label)

        self.ffmpeg_version_label = QLabel("Checking version...")
        self.configure_about_status_label(self.ffmpeg_version_label)
        self.ffmpeg_version_label.setStyleSheet(
            f"color: {self.COLORS['text_secondary']}; font-style: italic;"
        )
        ffmpeg_layout.addWidget(self.ffmpeg_version_label)

        ffmpeg_layout.addSpacing(10)

        ffmpeg_info = QLabel(
            'Used for merging video<br>'
            'and audio streams.<br><br><br>'
            'GitHub: <a href="https://github.com/FFmpeg/FFmpeg">FFmpeg/FFmpeg</a>'
        )
        ffmpeg_info.setWordWrap(True)
        ffmpeg_info.setTextFormat(Qt.TextFormat.RichText)
        ffmpeg_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        ffmpeg_info.setOpenExternalLinks(True)
        ffmpeg_layout.addWidget(ffmpeg_info)
        ffmpeg_layout.addStretch()

        powered_by_layout.addWidget(ffmpeg_widget, 1)

        layout.addWidget(powered_by_container, 0, Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch()

        layout.addSpacing(10)

        footer_label = QLabel("© 2025-2026 mme89")
        footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer_label.setStyleSheet(f"color: {self.COLORS['text_secondary']}; margin-top: 20px;")
        layout.addWidget(footer_label)

        self.tabs.addTab(about_widget, "About")

    def check_for_updates(self):
        """Check the GUI's published releases in the background."""
        if self.is_closing:
            return
        if self.update_checker.check():
            self.check_updates_button.setEnabled(False)
            self.update_status_label.setText("Checking for updates…")

    def on_update_check_finished(self, status, version, release_url):
        """Keep a release link in About and notify once per version per session."""
        if self.is_closing:
            return
        self.check_updates_button.setEnabled(True)
        if status == "error":
            self.update_status_label.setText("Could not check for updates. Please try again later.")
        elif status == "current":
            self.update_status_label.setText("You’re up to date with the latest stable release.")
        else:
            self.update_status_label.setText(
                f'Update available: {version}. <a href="{release_url}">View release</a>'
            )
            if version in self.notified_update_versions:
                return
            self.notified_update_versions.add(version)
            if self.update_notification is not None:
                self.update_notification.close()
            notification = QMessageBox(self)
            notification.setWindowTitle("Update Available")
            notification.setIcon(QMessageBox.Icon.Information)
            notification.setTextFormat(Qt.TextFormat.PlainText)
            notification.setText(
                f"yt-dlp GUI {version} is available. You’re running {APP_VERSION}."
            )
            notification.setInformativeText("Open the release page to download the new version.")
            notification.setStandardButtons(
                QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Close
            )
            notification.button(QMessageBox.StandardButton.Open).setText("View release")
            notification.setDefaultButton(QMessageBox.StandardButton.Close)
            notification.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            notification.buttonClicked.connect(
                lambda button: QDesktopServices.openUrl(QUrl(release_url))
                if notification.standardButton(button) == QMessageBox.StandardButton.Open else None
            )
            notification.finished.connect(self.on_update_notification_closed)
            self.update_notification = notification
            # Show without a nested event loop or blocking the main window.
            notification.setModal(False)
            notification.show()

    def on_update_notification_closed(self, _result):
        """Release the reference to the dismissed update notification."""
        self.update_notification = None

    def toggle_terminal_output(self, state):
        """Toggle visibility of terminal output window"""
        if Qt.CheckState(state) == Qt.CheckState.Checked:
            if not self.terminal_window:
                self.terminal_window = TerminalWindow(self)
                self.terminal_window.closed.connect(self.on_terminal_closed)
            self.terminal_window.show()
            self.terminal_window.raise_()
            self.terminal_window.activateWindow()
        else:
            if self.terminal_window:
                self.terminal_window.hide()

    def on_terminal_closed(self):
        """Handle terminal window being closed"""
        if self.is_closing:
            return
        self.show_terminal_checkbox.setChecked(False)

    def browse_destination(self):
        """Select and display a destination directory for downloads."""
        directory = QFileDialog.getExistingDirectory(self, "Select Download Directory")
        if directory:
            self.destination_input.setText(directory)

    def browse_ytdlp_path(self):
        """Select and display the yt-dlp executable path."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select yt-dlp Executable")
        if file_path:
            self.ytdlp_path_input.setText(file_path)

    def browse_ffmpeg_path(self):
        """Select and display the FFmpeg executable path."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select FFmpeg Executable")
        if file_path:
            self.ffmpeg_path_input.setText(file_path)

    def is_valid_url(self, url):
        """Validate if the URL is a valid YouTube/video URL"""
        if not url:
            return False

        url_pattern = re.compile(
            r'^https?://'
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
            r'localhost|'
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            r'(?::\d+)?'
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)

        return bool(url_pattern.match(url))

    def get_validated_url(self):
        """Return the current URL or show a warning when it is not usable."""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a URL first!")
            return None

        if not self.is_valid_url(url):
            QMessageBox.warning(
                self,
                "Invalid URL",
                "Please enter a valid URL (must start with http:// or https://)",
            )
            return None

        return url

    def find_executable(self, name):
        """Find executable in common locations across platforms"""
        if os.path.isfile(name) and os.access(name, os.X_OK):
            return name

        common_paths = []

        if sys.platform == 'darwin':
            common_paths = [
                f"/usr/local/bin/{name}",
                f"/opt/homebrew/bin/{name}",
                f"/opt/local/bin/{name}",
                f"/usr/bin/{name}",
                os.path.expanduser(f"~/.local/bin/{name}"),
            ]
        elif sys.platform == 'win32':
            exe_name = name if name.endswith('.exe') else f"{name}.exe"
            common_paths = [
                os.path.expanduser(f"~\\AppData\\Local\\Programs\\{name}\\{exe_name}"),
                os.path.expanduser(f"~\\AppData\\Local\\{name}\\{exe_name}"),
                f"C:\\Program Files\\{name}\\{exe_name}",
                f"C:\\Program Files (x86)\\{name}\\{exe_name}",
                os.path.expanduser(f"~\\scoop\\shims\\{exe_name}"),
                f"C:\\ProgramData\\chocolatey\\bin\\{exe_name}",
                f"C:\\Windows\\System32\\{exe_name}",
            ]
        else:
            common_paths = [
                f"/usr/local/bin/{name}",
                f"/usr/bin/{name}",
                f"/bin/{name}",
                f"/snap/bin/{name}",
                os.path.expanduser(f"~/.local/bin/{name}"),
            ]

        for path in common_paths:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path

        try:
            if sys.platform == 'win32':
                result = subprocess.run(
                    ['where', name],
                    capture_output=True,
                    text=True,
                    check=False,
                    **hidden_subprocess_kwargs(),
                )
            else:
                result = subprocess.run(
                    ['which', name], capture_output=True, text=True, check=False
                )

            if result.returncode == 0:
                found_path = result.stdout.strip().split('\n', maxsplit=1)[0]
                if found_path and os.path.isfile(found_path):
                    return found_path
        except (OSError, subprocess.SubprocessError):
            pass

        return name

    def get_ytdlp_path(self):
        """Get the yt-dlp path from settings"""
        ytdlp_path = self.ytdlp_path_input.text().strip()
        if ytdlp_path:
            return os.path.expanduser(ytdlp_path)
        return self.find_executable("yt-dlp")

    def find_available_executable(self, *names):
        """Return the first available executable path from the provided names."""
        for name in names:
            path = shutil.which(name)
            if path:
                return path

            detected_path = self.find_executable(name)
            if detected_path != name:
                return detected_path

        return None

    def invalidate_js_runtime_cache(self, *_args):
        """Mark JS runtime detection stale after relevant settings change."""
        self.js_runtime_info = None
        self.js_runtime_cache_dirty = True

    def detect_js_runtime(self, force_refresh=False):
        """Return cached JS runtime details, detecting them when needed."""
        if not force_refresh and not self.js_runtime_cache_dirty:
            return self.js_runtime_info

        self.js_runtime_info = self._detect_js_runtime()
        self.js_runtime_cache_dirty = False
        return self.js_runtime_info

    def _detect_js_runtime(self):
        """Detect the JS runtime yt-dlp will use."""
        custom_args = self.get_custom_options_args()
        if "--no-js-runtimes" in custom_args:
            return {
                "source": "custom",
                "name": "Custom runtime configuration",
                "path": "",
                "spec": "See custom options",
            }
        for index, arg in enumerate(custom_args):
            runtime_spec = None
            if arg == "--js-runtimes" and index + 1 < len(custom_args):
                runtime_spec = custom_args[index + 1]
            elif arg.startswith("--js-runtimes="):
                runtime_spec = arg.split("=", 1)[1]

            if not runtime_spec:
                continue

            runtime_entry = runtime_spec.split(",", 1)[0]
            runtime_name, _, runtime_path = runtime_entry.partition(":")
            runtime_name = runtime_name.strip()
            runtime_path = runtime_path.strip()

            display_names = {
                "deno": "Deno",
                "node": "Node",
                "nodejs": "Node",
                "bun": "Bun",
                "quickjs": "QuickJS",
                "qjs": "QuickJS",
            }
            executable_names = {
                "deno": ("deno",),
                "node": ("node", "nodejs"),
                "nodejs": ("node", "nodejs"),
                "bun": ("bun",),
                "quickjs": ("qjs",),
                "qjs": ("qjs",),
            }

            if not runtime_path and runtime_name in executable_names:
                runtime_path = self.find_available_executable(*executable_names[runtime_name]) or ""

            return {
                "source": "custom",
                "name": display_names.get(runtime_name, runtime_name or "Custom"),
                "path": runtime_path,
                "spec": runtime_spec,
            }

        runtime_candidates = (
            ("Deno", "deno", ("deno",)),
            ("Node", "node", ("node", "nodejs")),
            ("QuickJS", "quickjs", ("qjs",)),
            ("Bun", "bun", ("bun",)),
        )
        for display_name, runtime_name, executable_names in runtime_candidates:
            runtime_path = self.find_available_executable(*executable_names)
            if not runtime_path:
                continue
            version_line = self.get_runtime_version(display_name, runtime_path)
            if is_supported_runtime(display_name, version_line):
                return {
                    "source": "auto",
                    "name": display_name,
                    "path": runtime_path,
                    "spec": f"{runtime_name}:{runtime_path}",
                    "version": version_line,
                }

        return None

    def get_js_runtime_args(self):
        """Auto-enable a supported JS runtime for yt-dlp when one is available."""
        runtime_info = self.detect_js_runtime()
        if not runtime_info or runtime_info["source"] == "custom":
            return []

        return ["--js-runtimes", runtime_info["spec"]]

    def get_executable_version(
        self, executable_path, version_args=("--version",), success_codes=(0,)
    ):
        """Return the first line of version output, with a bounded timeout."""
        try:
            result = subprocess.run(
                [executable_path, *version_args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=3,
                **hidden_subprocess_kwargs(),
            )
        except (OSError, subprocess.SubprocessError, ValueError):
            return None

        if result.returncode in success_codes:
            output = (result.stdout or result.stderr or "").strip()
            if output:
                return output.splitlines()[0]
        return None

    def get_runtime_version(self, runtime_name, runtime_path):
        """QuickJS reports its version in help output rather than --version."""
        if os.path.isdir(runtime_path):
            executable_name = {
                "Deno": "deno", "Node": "node", "QuickJS": "qjs", "Bun": "bun",
            }.get(runtime_name)
            if not executable_name:
                return None
            if sys.platform == "win32":
                executable_name += ".exe"
            runtime_path = os.path.join(runtime_path, executable_name)
        version_args = ("--help",) if runtime_name == "QuickJS" else ("--version",)
        # QuickJS's help command returns 1 even when it prints valid version output.
        success_codes = (0, 1) if runtime_name == "QuickJS" else (0,)
        return self.get_executable_version(runtime_path, version_args, success_codes)

    def check_js_runtime_version(self):
        """Check which JS runtime yt-dlp will use and display its status."""
        runtime_info = self.detect_js_runtime(force_refresh=True)

        if not runtime_info:
            self.js_runtime_version = "Not found"
            self.js_runtime_version_label.setText(
                "⚠️ No supported JS runtime found (Deno 2.3+ or Node.js 22+ recommended)"
            )
            self.js_runtime_version_label.setStyleSheet(
                f"color: {self.COLORS['warning']}; font-style: italic;"
            )
            return

        version_line = runtime_info.get("version")
        if version_line is None and runtime_info["path"]:
            version_line = self.get_runtime_version(runtime_info["name"], runtime_info["path"])

        if version_line and not is_supported_runtime(runtime_info["name"], version_line):
            self.js_runtime_version = version_line
            self.js_runtime_version_label.setText(
                f"⚠️ Unsupported or unrecognized: {runtime_info['name']} {version_line}"
            )
            self.js_runtime_version_label.setStyleSheet(
                f"color: {self.COLORS['warning']}; font-weight: bold;"
            )
        elif version_line:
            self.js_runtime_version = version_line
            prefix = "Configured" if runtime_info["source"] == "custom" else "Using"
            self.js_runtime_version_label.setText(
                f"{prefix}: {runtime_info['name']} {version_line}"
                + (" (deprecated)" if runtime_info["name"] == "Bun" else "")
            )
            color = self.COLORS['warning' if runtime_info['name'] == 'Bun' else 'success']
            self.js_runtime_version_label.setStyleSheet(f"color: {color}; font-weight: bold;")
        elif runtime_info["source"] == "custom":
            self.js_runtime_version = runtime_info["spec"]
            self.js_runtime_version_label.setText(
                f"Configured (not verified): {runtime_info['spec']}"
            )
            self.js_runtime_version_label.setStyleSheet(
                f"color: {self.COLORS['info']}; font-weight: bold;"
            )
        else:
            self.js_runtime_version = runtime_info["name"]
            self.js_runtime_version_label.setText(f"Using: {runtime_info['name']}")
            self.js_runtime_version_label.setStyleSheet(
                f"color: {self.COLORS['success']}; font-weight: bold;"
            )

    def check_ytdlp_ejs_status(self):
        """The GUI's Python packages do not describe the external yt-dlp install."""
        self.ytdlp_ejs_status = "Not verified"
        self.ytdlp_ejs_status_label.setText("Managed by your yt-dlp installation (not verified)")
        self.ytdlp_ejs_status_label.setStyleSheet(
            f"color: {self.COLORS['info']}; font-weight: bold;"
        )

    def check_ytdlp_version(self):
        """Check if yt-dlp is installed and get version"""
        process = None
        try:
            ytdlp_path = self.get_ytdlp_path()
            if sys.platform == 'win32':
                result = subprocess.run(
                    [ytdlp_path, "--version"],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    check=False,
                    timeout=3,
                    **hidden_subprocess_kwargs(),
                )
                exit_code = result.returncode
                stdout = result.stdout or ""
            else:
                process = QProcess()
                process.start(ytdlp_path, ["--version"])
                process.waitForFinished(3000)
                exit_code = process.exitCode()
                stdout = bytes(process.readAllStandardOutput().data()).decode('utf-8')

            if exit_code == 0:
                version = stdout.strip()
                self.ytdlp_version = version
                update_recommended = needs_ytdlp_update(version)
                self.ytdlp_version_label.setText(
                    f"Installed version: {version}"
                    + (f" — update to {RECOMMENDED_YTDLP_VERSION}+ recommended"
                       if update_recommended else "")
                )
                color = self.COLORS['warning' if update_recommended else 'success']
                self.ytdlp_version_label.setStyleSheet(f"color: {color}; font-weight: bold;")
                self.statusBar().showMessage(f"yt-dlp {version} detected", 3000)
            else:
                self.ytdlp_version = "Not found"
                self.ytdlp_version_label.setText("⚠️ yt-dlp not found - Please install it")
                self.ytdlp_version_label.setStyleSheet(
                    f"color: {self.COLORS['error']}; font-weight: bold;"
                )

                if sys.platform == 'darwin':
                    install_msg = (
                        "yt-dlp is not installed or not in your PATH.\n\n"
                        "Please install it:\n"
                        "• Using Homebrew: brew install yt-dlp\n"
                        "• Or visit: https://github.com/yt-dlp/yt-dlp"
                    )
                elif sys.platform == 'win32':
                    install_msg = (
                        "yt-dlp is not installed or not in your PATH.\n\n"
                        "Please install it:\n"
                        "• Using winget: winget install yt-dlp\n"
                        "• Using Chocolatey: choco install yt-dlp\n"
                        "• Or visit: https://github.com/yt-dlp/yt-dlp"
                    )
                else:
                    install_msg = (
                        "yt-dlp is not installed or not in your PATH.\n\n"
                        "Please install it:\n"
                        '• Using pip (Python 3.11+): pip install -U "yt-dlp[default]"\n'
                        "• Using your package manager (e.g., apt, dnf, pacman)\n"
                        "• Or visit: https://github.com/yt-dlp/yt-dlp"
                    )

                QMessageBox.warning(self, "yt-dlp Not Found", install_msg)
        except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as e:
            self.ytdlp_version = "Error checking version"
            self.ytdlp_version_label.setText("Error checking yt-dlp version")
            self.ytdlp_version_label.setStyleSheet(f"color: {self.COLORS['warning']};")
            print(f"Error checking yt-dlp version: {e}")
        finally:
            if process:
                process.kill()
                process.waitForFinished(500)
                process.deleteLater()

    def get_ffmpeg_path(self):
        """Get the ffmpeg path from settings"""
        ffmpeg_path = self.ffmpeg_path_input.text().strip()
        if ffmpeg_path:
            return os.path.expanduser(ffmpeg_path)
        return self.find_executable("ffmpeg")

    def check_ffmpeg_version(self):
        """Check if FFmpeg is installed and get version"""
        process = None
        try:
            ffmpeg_path = self.get_ffmpeg_path()
            if sys.platform == 'win32':
                result = subprocess.run(
                    [ffmpeg_path, "-version"],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    check=False,
                    timeout=3,
                    **hidden_subprocess_kwargs(),
                )
                exit_code = result.returncode
                output = result.stdout or ""
            else:
                process = QProcess()
                process.start(ffmpeg_path, ["-version"])
                process.waitForFinished(3000)
                exit_code = process.exitCode()
                output = bytes(process.readAllStandardOutput().data()).decode('utf-8')

            if exit_code == 0:
                first_line = output.split('\n', maxsplit=1)[0]
                if 'version' in first_line:
                    version = first_line.split('version')[1].strip().split()[0]
                    self.ffmpeg_version = version
                    self.ffmpeg_version_label.setText(f"Installed version: {version}")
                    self.ffmpeg_version_label.setStyleSheet(
                        f"color: {self.COLORS['success']}; font-weight: bold;"
                    )
                else:
                    self.ffmpeg_version = "Unknown"
                    self.ffmpeg_version_label.setText("Installed (version unknown)")
                    self.ffmpeg_version_label.setStyleSheet(f"color: {self.COLORS['success']};")
            else:
                self.ffmpeg_version = "Not found"
                self.ffmpeg_version_label.setText("⚠️ FFmpeg not found (optional)")
                self.ffmpeg_version_label.setStyleSheet(
                    f"color: {self.COLORS['warning']}; font-style: italic;"
                )
        except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as e:
            self.ffmpeg_version = "Error checking version"
            self.ffmpeg_version_label.setText("FFmpeg status unknown")
            self.ffmpeg_version_label.setStyleSheet(
                f"color: {self.COLORS['text_secondary']}; font-style: italic;"
            )
            print(f"Error checking FFmpeg version: {e}")
        finally:
            if process:
                process.kill()
                process.waitForFinished(500)
                process.deleteLater()

    def fetch_formats(self):
        """Validate the URL and start fetching video metadata in the background."""
        if self.format_fetcher and self.format_fetcher.isRunning():
            self.download_page_status_label.setText("Already fetching formats...")
            return

        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a URL first!")
            return

        if not self.is_valid_url(url):
            QMessageBox.warning(
                self,
                "Invalid URL",
                "Please enter a valid URL (must start with http:// or https://)",
            )
            return

        self.download_page_status_label.setText("Fetching formats...")
        self.analyze_btn.setEnabled(False)

        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.status_label.setText("")

        if self.terminal_window and self.terminal_window.isVisible():
            self.terminal_window.clear()

        args_without_url = self.build_ytdlp_args(["-J"])
        if args_without_url is None:
            self.download_page_status_label.setText("Ready")
            self.analyze_btn.setEnabled(True)
            return

        self.format_fetcher = FormatFetcher(
            url,
            self.get_ytdlp_path(),
            args_without_url=args_without_url,
        )
        self.format_fetcher.finished.connect(self.on_formats_fetched)
        self.format_fetcher.error.connect(self.on_fetch_error)

        if self.terminal_window and self.terminal_window.isVisible():
            self.connect_worker_output(self.format_fetcher, self.terminal_window)

        self.format_fetcher.start()

    def on_formats_fetched(self, data):
        """Populate format selectors and video details from the active fetcher."""
        fetcher = self.sender()
        if fetcher is not self.format_fetcher:
            if fetcher:
                fetcher.deleteLater()
            return

        self.format_fetcher = None
        if fetcher:
            fetcher.deleteLater()
        if self.is_closing:
            return

        formats = data.get('formats', [])
        self.subtitles = data.get('subtitles', {})
        self.automatic_captions = data.get('automatic_captions', {})

        self.video_combo.clear()
        self.audio_combo.clear()
        self.subtitle_combo.clear()

        video_formats = []
        audio_formats = []
        self.format_data = {}

        for fmt in formats:
            format_id = fmt.get('format_id', '')
            ext = fmt.get('ext', '')
            vcodec = fmt.get('vcodec', 'none')
            acodec = fmt.get('acodec', 'none')
            resolution = fmt.get('resolution', 'audio only')
            fps = fmt.get('fps', 0)
            abr = fmt.get('abr', 0)
            filesize = fmt.get('filesize', 0)

            if filesize:
                if filesize > 1024 * 1024 * 1024:
                    size_str = f"{filesize / (1024**3):.1f}GB"
                elif filesize > 1024 * 1024:
                    size_str = f"{filesize / (1024**2):.1f}MB"
                else:
                    size_str = f"{filesize / 1024:.1f}KB"
            else:
                size_str = ""

            self.format_data[format_id] = fmt

            if vcodec != 'none' and acodec == 'none':
                fps_str = f" {fps}fps" if fps else ""
                size_part = f" ({size_str})" if size_str else ""
                label = f"{format_id}: {resolution} {ext}{fps_str}{size_part}"
                video_formats.append((label, format_id, fmt))
            elif acodec != 'none' and vcodec == 'none':
                abr_str = f"{abr}kbps" if abr else "unknown bitrate"
                size_part = f" ({size_str})" if size_str else ""
                label = f"{format_id}: {ext} {abr_str}{size_part}"
                audio_formats.append((label, format_id, fmt))

        self.video_combo.addItem("Best video", "bestvideo")
        video_formats.sort(key=lambda x: x[2].get('height', 0), reverse=True)
        for label, fid, _ in video_formats[:20]:
            self.video_combo.addItem(label, fid)
        self.video_combo.addItem("No video (audio only)", "none")

        self.audio_combo.addItem("Best audio", "bestaudio")
        audio_formats.sort(key=lambda x: x[2].get('abr', 0), reverse=True)
        for label, fid, _ in audio_formats[:15]:
            self.audio_combo.addItem(label, fid)
        self.audio_combo.addItem("No audio (video only)", "none")

        self.subtitle_combo.addItem("None", "")

        show_auto_captions = self.show_auto_captions_checkbox.isChecked()
        has_subtitles = bool(self.subtitles or (self.automatic_captions and show_auto_captions))

        if has_subtitles:
            self.subtitle_combo.addItem("All subtitles", "all")

            if self.subtitles:
                for lang_code in sorted(self.subtitles.keys()):
                    self.subtitle_combo.addItem(f"{lang_code} (manual)", lang_code)

            if self.automatic_captions and show_auto_captions:
                for lang_code in sorted(self.automatic_captions.keys()):
                    if lang_code not in self.subtitles:
                        self.subtitle_combo.addItem(f"{lang_code} (auto)", lang_code)
        else:
            self.subtitle_combo.addItem("English (if available)", "en")

        self.update_subtitle_option_states()

        title = data.get('title', 'Unknown')
        duration = data.get('duration', 0)
        uploader = data.get('uploader', 'Unknown')
        upload_date = data.get('upload_date', '')
        view_count = data.get('view_count', 0)
        like_count = data.get('like_count', 0)
        dislike_count = data.get('dislike_count', 0)

        if duration:
            hours = int(duration // 3600)
            minutes = int((duration % 3600) // 60)
            seconds = int(duration % 60)
            if hours > 0:
                duration_str = f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                duration_str = f"{minutes}:{seconds:02d}"
        else:
            duration_str = "Unknown"

        if upload_date and len(upload_date) == 8:
            year = upload_date[0:4]
            month = upload_date[4:6]
            day = upload_date[6:8]
            upload_date_str = f"{year}-{month}-{day}"
        else:
            upload_date_str = "Unknown"

        if view_count:
            if view_count >= 1_000_000:
                views_str = f"{view_count / 1_000_000:.1f}M views"
            elif view_count >= 1_000:
                views_str = f"{view_count / 1_000:.1f}K views"
            else:
                views_str = f"{view_count} views"
        else:
            views_str = "Unknown"

        def format_count(count):
            """Format a viewer count using compact thousands or millions suffixes."""
            if count >= 1_000_000:
                return f"{count / 1_000_000:.1f}M"
            if count >= 1_000:
                return f"{count / 1_000:.1f}K"
            return str(count)

        likes_parts = []
        if like_count:
            likes_parts.append(f"👍 {format_count(like_count)}")
        if dislike_count:
            likes_parts.append(f"👎 {format_count(dislike_count)}")

        if likes_parts:
            likes_str = " | ".join(likes_parts)
        elif like_count == 0 and dislike_count == 0:
            likes_str = "No data available"
        else:
            likes_str = "Unknown"

        self.title_label.setText(f"Title: {title}")
        self.duration_label.setText(f"Duration: {duration_str}")
        self.uploader_label.setText(f"Uploader: {uploader}")
        self.upload_date_label.setText(f"Uploaded: {upload_date_str}")
        self.views_label.setText(f"Views: {views_str}")
        self.likes_label.setText(f"Likes: {likes_str}")

        thumbnail_url = data.get('thumbnail', '')
        if thumbnail_url:
            self.load_thumbnail(thumbnail_url)
        else:
            self.thumbnail_label.setText("No thumbnail available")

        self.download_page_status_label.setText(
            f"Loaded {len(video_formats)} video + {len(audio_formats)} audio formats"
        )
        self.analyze_btn.setEnabled(True)

    def on_fetch_error(self, error):
        """Restore download controls and report an active metadata fetch failure."""
        fetcher = self.sender()
        if fetcher is not self.format_fetcher:
            if fetcher:
                fetcher.deleteLater()
            return

        self.format_fetcher = None
        if fetcher:
            fetcher.deleteLater()
        if self.is_closing:
            return

        QMessageBox.critical(self, "Error", f"Failed to fetch formats: {error}")
        self.download_page_status_label.setText("Error fetching formats")
        self.analyze_btn.setEnabled(True)

    def refresh_subtitle_dropdown(self):
        """Refresh subtitle dropdown when auto-captions checkbox is toggled"""
        if not hasattr(self, 'subtitles') or not hasattr(self, 'automatic_captions'):
            return

        current_selection = self.subtitle_combo.currentData()

        self.subtitle_combo.clear()
        self.subtitle_combo.addItem("None", "")

        show_auto_captions = self.show_auto_captions_checkbox.isChecked()
        has_subtitles = bool(self.subtitles or (self.automatic_captions and show_auto_captions))

        if has_subtitles:
            self.subtitle_combo.addItem("All subtitles", "all")

            if self.subtitles:
                for lang_code in sorted(self.subtitles.keys()):
                    self.subtitle_combo.addItem(f"{lang_code} (manual)", lang_code)

            if self.automatic_captions and show_auto_captions:
                for lang_code in sorted(self.automatic_captions.keys()):
                    if lang_code not in self.subtitles:
                        self.subtitle_combo.addItem(f"{lang_code} (auto)", lang_code)
        else:
            self.subtitle_combo.addItem("English (if available)", "en")

        for i in range(self.subtitle_combo.count()):
            if self.subtitle_combo.itemData(i) == current_selection:
                self.subtitle_combo.setCurrentIndex(i)
                break

        self.update_subtitle_option_states()

    def on_show_auto_captions_changed(self, *_args):
        """Handle auto-caption visibility changes."""
        self.refresh_subtitle_dropdown()
        self.schedule_settings_save()

    def update_subtitle_option_states(self):
        """Update subtitle-related option states based on the current selection."""
        subtitle_lang = self.subtitle_combo.currentData()
        include_all_subtitles = subtitle_lang == "all"
        self.include_live_chat_checkbox.setEnabled(include_all_subtitles)
        self.keep_subtitle_files_checkbox.setEnabled(bool(subtitle_lang))

    def get_all_subtitle_langs_value(self):
        """Return the subtitle language selector for the 'all subtitles' option."""
        if self.include_live_chat_checkbox.isChecked():
            return "all"
        return "all,-live_chat"

    def subtitle_selection_includes_auto_captions(self, subtitle_lang):
        """Return whether the current subtitle selection needs auto-caption output."""
        if not getattr(self, "automatic_captions", None):
            return False

        if subtitle_lang == "all":
            return self.show_auto_captions_checkbox.isChecked()

        return (
            subtitle_lang in self.automatic_captions
            and self.subtitle_combo.currentText().endswith("(auto)")
        )

    def add_subtitle_args(self, args):
        """Append subtitle-related yt-dlp arguments based on the current UI state."""
        subtitle_lang = self.subtitle_combo.currentData()
        if not subtitle_lang:
            return

        args.append("--embed-subs")
        if self.subtitle_selection_includes_auto_captions(subtitle_lang):
            args.append("--write-auto-subs")
        if self.keep_subtitle_files_checkbox.isChecked():
            args.append("--write-subs")

        if subtitle_lang != "all":
            args.extend(["--sub-langs", subtitle_lang])
        else:
            args.extend(["--sub-langs", self.get_all_subtitle_langs_value()])

    def load_thumbnail(self, url):
        """Load thumbnail using QtNetwork for better PyInstaller compatibility"""
        try:
            if self.active_thumbnail_reply:
                self.active_thumbnail_reply.abort()
                self.active_thumbnail_reply.deleteLater()
                self.active_thumbnail_reply = None
            request = QNetworkRequest(QUrl(url))
            self.active_thumbnail_reply = self.network_manager.get(request)
            self.active_thumbnail_reply.finished.connect(self.on_thumbnail_loaded)
        except (RuntimeError, TypeError, ValueError):
            self.thumbnail_label.setText("Failed to load thumbnail")

    def on_thumbnail_loaded(self):
        """Handle thumbnail download completion"""
        reply = self.active_thumbnail_reply
        if not reply:
            return

        try:
            if self.is_closing:
                return
            if reply.error() == QNetworkReply.NetworkError.NoError:
                image_data = reply.readAll()
                pixmap = QPixmap()
                if pixmap.loadFromData(image_data):
                    self.thumbnail_label.setPixmap(pixmap)
                else:
                    self.thumbnail_label.setText("Failed to load thumbnail")
            else:
                error_string = reply.errorString()
                print(f"Network error loading thumbnail: {error_string}")
                self.thumbnail_label.setText("Failed to load thumbnail")
        except (RuntimeError, TypeError, ValueError) as e:
            print(f"Exception loading thumbnail: {e}")
            self.thumbnail_label.setText("Failed to load thumbnail")
        finally:
            if reply == self.active_thumbnail_reply:
                self.active_thumbnail_reply = None
            reply.deleteLater()

    def append_worker_output(self, output_widget, text):
        """Append worker output to a caller-selected widget."""
        if self.is_closing:
            return

        if output_widget:
            output_widget.append(text)

    def connect_worker_output(self, worker, output_widget):
        """Route a worker's text output signal to a specific widget."""
        if output_widget:
            worker.output.connect(
                lambda text, widget=output_widget: self.append_worker_output(widget, text)
            )

    def on_download_thread_finished(self, exit_code):
        """Dispatch normal download completion based on the sending thread."""
        thread = self.sender()
        is_download = getattr(thread, "is_download", True)
        stop_requested = getattr(thread, "stop_requested", False)
        self.on_download_finished(exit_code, is_download, stop_requested)

    def is_ytdlp_command_running(self):
        """Return True while a download/custom yt-dlp command thread is active."""
        return bool(self.download_thread and self.download_thread.isRunning())

    def warn_if_ytdlp_command_running(self):
        """Show a warning if starting another command would replace active state."""
        if not self.is_ytdlp_command_running():
            return False

        QMessageBox.warning(
            self,
            "Command Running",
            "A yt-dlp command is already running. Please wait for it to finish or abort it first.",
        )
        return True

    def set_command_controls_enabled(self, enabled):
        """Enable or disable controls that start yt-dlp command threads."""
        can_start = enabled and not self.is_processing_queue and not self.is_ytdlp_command_running()

        self.download_btn.setEnabled(can_start)
        self.add_to_queue_btn.setEnabled(can_start)
        self.execute_custom_btn.setEnabled(can_start)
        self.metadata_btn.setEnabled(can_start)
        self.list_subs_btn.setEnabled(can_start)
        self.download_playlist_btn.setEnabled(can_start and self.playlist_table.rowCount() > 0)
        self.start_queue_btn.setEnabled(can_start and bool(self.download_queue))
        self.stop_queue_btn.setEnabled(self.is_processing_queue)

    def download_video(self):
        """Validate the selected video and start downloading the chosen formats."""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a URL first!")
            return

        if not self.is_valid_url(url):
            QMessageBox.warning(
                self,
                "Invalid URL",
                "Please enter a valid URL (must start with http:// or https://)",
            )
            return

        selection = self.build_selected_download_args()
        if not selection:
            return

        args, _, format_display = selection

        self.run_yt_dlp(args, is_download=True, format_display=format_display)

    def add_to_queue(self):
        """Add current video to download queue"""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a URL first!")
            return

        if not self.is_valid_url(url):
            QMessageBox.warning(
                self,
                "Invalid URL",
                "Please enter a valid URL (must start with http:// or https://)",
            )
            return

        selection = self.build_selected_download_args()
        if not selection:
            return

        args, format_id, format_display = selection

        title = (
            self.title_label.text().replace("Title: ", "")
            if self.title_label.text() != "Title: -"
            else "Unknown"
        )

        total_size = self.calculate_format_size(format_id)

        queue_item = {
            "url": url,
            "args": args,
            "format": format_id,
            "format_display": format_display,
            "title": title,
            "size": total_size,
            "status": "Pending"
        }
        self.download_queue.append(queue_item)
        self.update_queue_table()
        self.set_command_controls_enabled(True)

        QMessageBox.information(
            self,
            "Added to Queue",
            f"Video added to queue!\n\nTotal items in queue: {len(self.download_queue)}",
        )

    def update_queue_table(self):
        """Update the queue table display"""
        self.queue_table.setRowCount(len(self.download_queue))

        for i, item in enumerate(self.download_queue):
            index_item = QTableWidgetItem(str(i + 1))
            index_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.queue_table.setItem(i, 0, index_item)

            status_item = QTableWidgetItem(item["status"])
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if item["status"] == "Completed":
                status_item.setForeground(QColor(self.COLORS['success']))
            elif item["status"] == "Failed":
                status_item.setForeground(QColor(self.COLORS['error']))
            elif item["status"] == "Downloading":
                status_item.setForeground(QColor(self.COLORS['info']))
            elif item["status"] == "Aborted":
                status_item.setForeground(QColor(self.COLORS['warning']))
            self.queue_table.setItem(i, 1, status_item)

            url_display = item["url"][:50] + "..." if len(item["url"]) > 50 else item["url"]
            self.queue_table.setItem(i, 2, QTableWidgetItem(url_display))

            self.queue_table.setItem(i, 3, QTableWidgetItem(item["title"]))

            format_display = item.get("format_display", item["format"])
            format_item = QTableWidgetItem(format_display)
            format_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.queue_table.setItem(i, 4, format_item)

            size_display = item.get("size", "Unknown")
            size_item = QTableWidgetItem(size_display)
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.queue_table.setItem(i, 5, size_item)

        if len(self.download_queue) == 0:
            self.queue_status_label.setText("Queue is empty. Add videos from the Download tab.")
        else:
            completed = sum(1 for item in self.download_queue if item["status"] == "Completed")
            failed = sum(1 for item in self.download_queue if item["status"] == "Failed")
            pending = sum(1 for item in self.download_queue if item["status"] == "Pending")
            self.queue_status_label.setText(
                f"Total: {len(self.download_queue)} | Pending: {pending} | "
                f"Completed: {completed} | Failed: {failed}"
            )

    def start_queue_processing(self):
        """Start processing the download queue"""
        if not self.download_queue:
            QMessageBox.warning(self, "Error", "Queue is empty!")
            return

        if self.is_processing_queue:
            QMessageBox.warning(self, "Error", "Queue is already being processed!")
            return

        if self.warn_if_ytdlp_command_running():
            return

        self.is_processing_queue = True
        self.set_command_controls_enabled(False)
        self.statusBar().showMessage("Processing queue...")
        self.process_next_in_queue()

    def process_next_in_queue(self):
        """Process the next item in the queue"""
        if not self.is_processing_queue:
            return

        next_item = None
        for item in self.download_queue:
            if item["status"] == "Pending":
                next_item = item
                break

        if not next_item:
            self.is_processing_queue = False
            self.set_command_controls_enabled(True)
            self.progress_bar.setValue(0)
            self.progress_bar.setTextVisible(False)
            self.status_label.setText("")
            self.abort_btn.setEnabled(False)
            self.statusBar().showMessage("Queue processing completed!", 5000)
            QMessageBox.information(
                self,
                "Queue Complete",
                "All downloads in the queue have been processed!",
            )
            return

        next_item["status"] = "Downloading"
        self.current_queue_item = next_item
        self.update_queue_table()

        if not self.run_yt_dlp_queue(
            next_item["args"], next_item["url"], next_item.get("format_display", "")
        ):
            next_item["status"] = "Pending"
            self.current_queue_item = None
            self.is_processing_queue = False
            self.set_command_controls_enabled(True)
            self.update_queue_table()

    def run_yt_dlp_queue(self, args, url, format_display=""):
        """Run yt-dlp for queue item"""
        if self.warn_if_ytdlp_command_running():
            return False

        if format_display:
            output_template = f"%(title)s [{format_display}].%(ext)s"
        else:
            output_template = "%(title)s [%(format_id)s].%(ext)s"

        args = self.build_ytdlp_args(args, is_download=True, output_template=output_template)
        if args is None:
            return False

        if self.terminal_window and self.terminal_window.isVisible():
            self.terminal_window.append(f"\n{'='*60}\n")
            self.terminal_window.append(f"Queue: Processing {url}\n")
            self.terminal_window.append(f"Running: yt-dlp {' '.join(args)}\n")
            self.terminal_window.append(f"{'='*60}\n")

        self.set_command_controls_enabled(False)

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.status_label.setText("Starting download...")

        self.download_thread = DownloadThread(args, url, self.get_ytdlp_path())
        if self.terminal_window and self.terminal_window.isVisible():
            self.connect_worker_output(self.download_thread, self.terminal_window)
        self.download_thread.progress.connect(self.update_queue_progress)
        self.download_thread.finished_signal.connect(self.on_queue_download_finished)
        self.download_thread.start()
        return True

    def update_queue_progress(self, percentage, status):
        """Update progress bar and status label on Download page"""
        self.progress_bar.setValue(percentage)
        self.status_label.setText(status)

    def on_queue_download_finished(self, exit_code):
        """Handle completion of queue item download"""
        thread = self.sender()
        stop_requested = getattr(thread, "stop_requested", False)
        self.download_thread = None
        if self.is_closing:
            return

        was_aborted = stop_requested and exit_code != 0
        finished_item = self.current_queue_item
        self.current_queue_item = None

        if finished_item:
            if exit_code == 0:
                finished_item["status"] = "Completed"
            elif was_aborted:
                finished_item["status"] = "Aborted"
            else:
                finished_item["status"] = "Failed"
            self.update_queue_table()

        if self.is_processing_queue:
            self.process_next_in_queue()
        else:
            self.set_command_controls_enabled(True)

    def stop_queue_processing(self):
        """Stop processing the queue"""
        if not self.is_processing_queue:
            return

        reply = QMessageBox.question(
            self,
            "Stop Queue",
            "Stop processing the queue?\n\nThe current download will be aborted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.is_processing_queue = False
            self.set_command_controls_enabled(True)

            self.progress_bar.setValue(0)
            self.progress_bar.setTextVisible(False)
            self.status_label.setText("")
            self.abort_btn.setEnabled(False)

            if self.download_thread and self.download_thread.isRunning():
                self.download_thread.stop()

            if self.current_queue_item and self.current_queue_item["status"] == "Downloading":
                self.current_queue_item["status"] = "Pending"
                self.update_queue_table()
            self.current_queue_item = None

            self.statusBar().showMessage("Queue processing stopped", 3000)

    def clear_queue(self):
        """Clear all items from the queue"""
        if not self.download_queue:
            return

        reply = QMessageBox.question(
            self,
            "Clear Queue",
            f"Remove all {len(self.download_queue)} items from the queue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.download_queue.clear()
            self.update_queue_table()
            self.start_queue_btn.setEnabled(False)

    def remove_selected_from_queue(self):
        """Remove selected items from the queue"""
        selected_rows = set(item.row() for item in self.queue_table.selectedItems())

        if not selected_rows:
            QMessageBox.warning(self, "Error", "Please select items to remove!")
            return

        for row in selected_rows:
            if (
                row < len(self.download_queue)
                and self.download_queue[row]["status"] == "Downloading"
            ):
                QMessageBox.warning(
                    self,
                    "Error",
                    "Cannot remove item that is currently downloading!",
                )
                return

        reply = QMessageBox.question(
            self,
            "Remove Items",
            f"Remove {len(selected_rows)} selected item(s) from queue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            for row in sorted(selected_rows, reverse=True):
                if row < len(self.download_queue):
                    del self.download_queue[row]

            self.update_queue_table()

            if len(self.download_queue) == 0:
                self.start_queue_btn.setEnabled(False)

    def load_playlist_items(self):
        """Load playlist items and display in table"""
        if self.playlist_fetcher and self.playlist_fetcher.isRunning():
            self.playlist_status_label.setText("Already loading playlist...")
            return

        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a URL first!")
            return

        if not self.is_valid_url(url):
            QMessageBox.warning(
                self,
                "Invalid URL",
                "Please enter a valid URL (must start with http:// or https://)",
            )
            return

        self.playlist_status_label.setText("Loading playlist...")
        self.list_playlist_btn.setEnabled(False)
        self.playlist_table.setRowCount(0)

        args_without_url = self.build_ytdlp_args(["--flat-playlist", "-J"])
        if args_without_url is None:
            self.playlist_status_label.setText("Ready")
            self.list_playlist_btn.setEnabled(True)
            return

        self.playlist_fetcher = FormatFetcher(
            url,
            self.get_ytdlp_path(),
            args_without_url=args_without_url,
        )
        self.playlist_fetcher.finished.connect(self.on_playlist_loaded)
        self.playlist_fetcher.error.connect(self.on_playlist_error)

        if self.terminal_window and self.terminal_window.isVisible():
            self.connect_worker_output(self.playlist_fetcher, self.terminal_window)

        self.playlist_fetcher.start()

    def on_playlist_loaded(self, data):
        """Populate table with playlist items"""
        fetcher = self.sender()
        if fetcher is not self.playlist_fetcher:
            if fetcher:
                fetcher.deleteLater()
            return

        self.playlist_fetcher = None
        if fetcher:
            fetcher.deleteLater()
        if self.is_closing:
            return

        entries = data.get('entries', [])

        if not entries:
            self.playlist_status_label.setText("No videos found in playlist")
            self.list_playlist_btn.setEnabled(True)
            return

        self.playlist_table.setRowCount(len(entries))

        for i, entry in enumerate(entries):
            checkbox_item = QTableWidgetItem()
            checkbox_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            checkbox_item.setCheckState(Qt.CheckState.Checked)
            self.playlist_table.setItem(i, 0, checkbox_item)

            status_item = QTableWidgetItem("Pending")
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setForeground(QColor(self.COLORS['text_secondary']))
            self.playlist_table.setItem(i, 1, status_item)

            title = entry.get('title', 'Unknown')
            self.playlist_table.setItem(i, 2, QTableWidgetItem(title))

            duration = entry.get('duration', 0)
            if duration:
                hours = int(duration // 3600)
                minutes = int((duration % 3600) // 60)
                seconds = int(duration % 60)
                if hours > 0:
                    duration_str = f"{hours}:{minutes:02d}:{seconds:02d}"
                else:
                    duration_str = f"{minutes}:{seconds:02d}"
            else:
                duration_str = "Unknown"
            duration_item = QTableWidgetItem(duration_str)
            duration_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.playlist_table.setItem(i, 3, duration_item)

            uploader = entry.get('uploader', 'Unknown')
            self.playlist_table.setItem(i, 4, QTableWidgetItem(uploader))

        self.playlist_status_label.setText(
            f"Loaded {len(entries)} videos. Check videos to download"
        )
        self.list_playlist_btn.setEnabled(True)
        self.download_playlist_btn.setEnabled(
            not self.is_ytdlp_command_running() and not self.is_processing_queue
        )
        self.check_all_playlist_btn.setEnabled(True)
        self.uncheck_all_playlist_btn.setEnabled(True)

    def on_playlist_error(self, error):
        """Handle playlist loading error"""
        fetcher = self.sender()
        if fetcher is not self.playlist_fetcher:
            if fetcher:
                fetcher.deleteLater()
            return

        self.playlist_fetcher = None
        if fetcher:
            fetcher.deleteLater()
        if self.is_closing:
            return

        self.playlist_status_label.setText(f"Error: {error}")
        self.list_playlist_btn.setEnabled(True)
        QMessageBox.critical(self, "Error", f"Failed to load playlist: {error}")

    def download_playlist(self):
        """Download checked playlist items"""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a URL first!")
            return

        checked_rows = []
        for row in range(self.playlist_table.rowCount()):
            checkbox_item = self.playlist_table.item(row, 0)
            if checkbox_item and checkbox_item.checkState() == Qt.CheckState.Checked:
                checked_rows.append(row)

        if not checked_rows:
            QMessageBox.warning(self, "Error", "Please check at least one video to download!")
            return

        if self.warn_if_ytdlp_command_running():
            return

        for row in checked_rows:
            status_item = self.playlist_table.item(row, 1)
            if status_item:
                status_item.setText("Downloading")
                status_item.setForeground(QColor(self.COLORS['info']))

        items = ",".join(str(row + 1) for row in checked_rows)

        quality = self.playlist_quality_combo.currentData()
        if quality == "best":
            format_str = "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4] / bv*+ba/b"
        else:
            format_str = (
                f"bv*[height<={quality}][ext=mp4]+ba[ext=m4a]/"
                f"b[height<={quality}][ext=mp4] / "
                f"bv*[height<={quality}]+ba/b[height<={quality}]"
            )

        args = ["-f", format_str, "--merge-output-format", "mp4"]
        args.extend(["-I", items])

        self.current_playlist_downloads = checked_rows

        self.run_yt_dlp(args, is_download=True)

    def check_all_playlist(self):
        """Check all playlist items"""
        for row in range(self.playlist_table.rowCount()):
            checkbox_item = self.playlist_table.item(row, 0)
            if checkbox_item:
                checkbox_item.setCheckState(Qt.CheckState.Checked)

    def uncheck_all_playlist(self):
        """Uncheck all playlist items"""
        for row in range(self.playlist_table.rowCount()):
            checkbox_item = self.playlist_table.item(row, 0)
            if checkbox_item:
                checkbox_item.setCheckState(Qt.CheckState.Unchecked)

    def execute_custom(self):
        """Validate and run the custom yt-dlp arguments entered in the Advanced tab."""
        if self.get_validated_url() is None:
            return

        custom_args = self.custom_input.text().strip()
        if not custom_args:
            QMessageBox.warning(self, "Error", "Please enter custom arguments!")
            return

        try:
            args = shlex.split(custom_args)
        except ValueError as e:
            QMessageBox.warning(
                self, "Invalid Arguments", f"Could not parse custom arguments: {e}"
            )
            return

        self.run_yt_dlp(args, self.advanced_output)

    def get_metadata(self):
        """Print the selected video metadata in the Advanced tab."""
        if self.get_validated_url() is None:
            return

        self.run_yt_dlp(["--print", "%()j"], self.advanced_output)

    def list_subtitles(self):
        """Print available manual and automatic subtitle tables."""
        if self.get_validated_url() is None:
            return

        self.run_yt_dlp(
            ["--print", "automatic_captions_table", "--print", "subtitles_table"],
            self.advanced_output,
        )

    def run_yt_dlp(self, args, output_widget=None, *, is_download=False, format_display=""):
        """Build a command and start a worker with output and progress handlers."""
        if self.warn_if_ytdlp_command_running():
            return False

        url = self.url_input.text().strip()

        output_template = f"%(title)s [{format_display}].%(ext)s" if format_display else None
        args = self.build_ytdlp_args(args, is_download=is_download, output_template=output_template)
        if args is None:
            return False

        if self.terminal_window and self.terminal_window.isVisible():
            active_output_widget = self.terminal_window
            tab_widget = output_widget if not is_download else None
        elif is_download:
            active_output_widget = None
            tab_widget = None
        else:
            active_output_widget = output_widget
            tab_widget = None

        if active_output_widget:
            active_output_widget.clear()
            active_output_widget.append(f"Running: yt-dlp {' '.join(args)}\n")
            active_output_widget.append(f"URL: {url}\n")
            active_output_widget.append("-" * 60 + "\n")

        if tab_widget and tab_widget != active_output_widget:
            tab_widget.clear()
            tab_widget.append("═" * 60 + "\n")
            tab_widget.append("📺 Output is being shown in the Terminal Window\n")
            tab_widget.append("═" * 60 + "\n\n")
            tab_widget.append(
                "The detailed yt-dlp output is displayed in the separate terminal window.\n"
            )
            tab_widget.append("You can close the terminal window to see output here instead.\n")

        self.statusBar().showMessage("Running yt-dlp...")
        self.set_command_controls_enabled(False)

        if is_download:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.progress_bar.setTextVisible(True)
            self.status_label.setText("Starting download...")
            self.abort_btn.setEnabled(True)

        self.download_thread = DownloadThread(args, url, self.get_ytdlp_path())
        self.download_thread.is_download = is_download
        self.connect_worker_output(self.download_thread, active_output_widget)
        if is_download:
            self.download_thread.progress.connect(self.update_progress)
        self.download_thread.finished_signal.connect(self.on_download_thread_finished)
        self.download_thread.start()
        return True

    def update_progress(self, percentage, status):
        """Update progress bar and status label"""
        self.progress_bar.setValue(percentage)
        self.status_label.setText(status)

    def abort_download(self):
        """Abort the current download"""
        if not self.download_thread or not self.download_thread.isRunning():
            return

        reply = QMessageBox.question(
            self,
            "Abort Download",
            "Are you sure you want to abort the current download?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.status_label.setText("Aborting download...")
            self.abort_btn.setEnabled(False)

            self.download_thread.stop()

    def on_download_finished(self, exit_code, is_download, stop_requested=False):
        """Restore controls and update the queue after a command finishes."""
        self.download_thread = None
        if self.is_closing:
            return

        was_aborted = stop_requested and exit_code != 0

        if self.terminal_window and self.terminal_window.isVisible():
            self.terminal_window.append("\n" + "-" * 60 + "\n")
            if exit_code == 0:
                self.terminal_window.append("✓ Command completed successfully!\n")
            elif was_aborted:
                self.terminal_window.append("⚠ Download aborted by user\n")
            else:
                self.terminal_window.append(f"✗ Command failed with exit code {exit_code}\n")

        if exit_code == 0:
            self.statusBar().showMessage("Command completed successfully!", 5000)
            if is_download:
                self.progress_bar.setValue(100)
                self.status_label.setText("✓ Download completed successfully!")
                self.abort_btn.setEnabled(False)
                for row in self.current_playlist_downloads:
                    status_item = self.playlist_table.item(row, 1)
                    if status_item:
                        status_item.setText("Completed")
                        status_item.setForeground(QColor(self.COLORS['success']))
                self.current_playlist_downloads = []
        elif was_aborted:
            self.statusBar().showMessage("Download aborted", 5000)
            if is_download:
                self.status_label.setText("⚠ Download aborted by user")
                self.abort_btn.setEnabled(False)
                for row in self.current_playlist_downloads:
                    status_item = self.playlist_table.item(row, 1)
                    if status_item:
                        status_item.setText("Aborted")
                        status_item.setForeground(QColor(self.COLORS['warning']))
                self.current_playlist_downloads = []
        else:
            self.statusBar().showMessage(f"Command failed with exit code {exit_code}", 5000)
            if is_download:
                self.status_label.setText(f"✗ Download failed with exit code {exit_code}")
                self.abort_btn.setEnabled(False)
                for row in self.current_playlist_downloads:
                    status_item = self.playlist_table.item(row, 1)
                    if status_item:
                        status_item.setText("Failed")
                        status_item.setForeground(QColor(self.COLORS['error']))
                self.current_playlist_downloads = []

        self.set_command_controls_enabled(True)

    def stop_worker_thread(self, thread, timeout_ms=3000):
        """Stop a worker thread without using QThread.terminate()."""
        if not thread or not thread.isRunning():
            return True

        if hasattr(thread, "stop_and_wait"):
            thread.stop_and_wait(timeout_ms)
        elif hasattr(thread, "stop"):
            thread.stop(force=True)

        return thread.wait(timeout_ms)

    def cleanup_for_exit(self, interactive=True):
        """Tear down background activity and Qt objects before interpreter shutdown."""
        self.is_closing = True
        self.update_startup_timer.stop()
        self.update_timer.stop()
        self.update_checker.cancel()
        if self.update_notification is not None:
            self.update_notification.close()

        if self.active_thumbnail_reply:
            try:
                self.active_thumbnail_reply.abort()
                self.active_thumbnail_reply.finished.disconnect(self.on_thumbnail_loaded)
            except (RuntimeError, TypeError):
                pass
            self.active_thumbnail_reply.deleteLater()
            self.active_thumbnail_reply = None

        download_stopped = self.stop_worker_thread(self.download_thread)
        format_fetcher_stopped = self.stop_worker_thread(self.format_fetcher)
        playlist_fetcher_stopped = self.stop_worker_thread(self.playlist_fetcher)

        if not download_stopped or not format_fetcher_stopped or not playlist_fetcher_stopped:
            if interactive:
                self.is_closing = False
                QMessageBox.warning(
                    self,
                    "Please Wait",
                    "A background task is still shutting down. "
                    "Please wait a moment and try closing the app again.",
                )
            return False

        self.download_thread = None
        self.format_fetcher = None
        self.playlist_fetcher = None

        if self.settings_save_timer and self.settings_save_timer.isActive():
            self.settings_save_timer.stop()
            self.save_settings(show_feedback=False)

        if self.terminal_window:
            try:
                self.terminal_window.closed.disconnect(self.on_terminal_closed)
            except (RuntimeError, TypeError):
                pass
            self.terminal_window.close()
            self.terminal_window.deleteLater()
            self.terminal_window = None

        return True

    def closeEvent(self, event):
        """Handle application close - cleanup running processes"""
        if not self.cleanup_for_exit(interactive=True):
            event.ignore()
            return

        event.accept()

    def get_config_file_path(self):
        """Return the settings path, using a persistent user directory for packaged apps."""
        if sys.platform == 'win32' or getattr(sys, 'frozen', False):
            config_dir = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppConfigLocation
            )
            if config_dir:
                return Path(config_dir) / "settings.json"

        return self.legacy_config_file

    def load_settings(self):
        """Load saved preferences and migrate legacy settings when needed."""
        try:
            config_file = self.config_file
            migrate_legacy_settings = False
            if not config_file.exists() and self.legacy_config_file != config_file:
                if self.legacy_config_file.exists():
                    config_file = self.legacy_config_file
                    migrate_legacy_settings = True

            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)

                self.destination_input.setText(settings.get("destination", ""))
                self.ytdlp_path_input.setText(settings.get("ytdlp_path", ""))
                self.ffmpeg_path_input.setText(settings.get("ffmpeg_path", ""))
                self.custom_options_input.setText(settings.get("custom_options", ""))
                self.limit_rate_input.setText(settings.get("limit_rate", ""))
                self.throttled_rate_input.setText(settings.get("throttled_rate", ""))
                self.show_auto_captions_checkbox.setChecked(
                    settings.get("show_auto_captions", False)
                )

                if migrate_legacy_settings:
                    self.config_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(self.config_file, 'w', encoding='utf-8') as f:
                        json.dump(settings, f, indent=2)
        except (OSError, json.JSONDecodeError, TypeError) as e:
            print(f"Error loading settings: {e}")

    def setup_settings_autosave(self):
        """Autosave settings shortly after option fields change."""
        self.settings_save_timer = QTimer(self)
        self.settings_save_timer.setSingleShot(True)
        self.settings_save_timer.setInterval(750)
        self.settings_save_timer.timeout.connect(lambda: self.save_settings(show_feedback=False))

        for input_widget in (
            self.destination_input,
            self.ytdlp_path_input,
            self.ffmpeg_path_input,
            self.custom_options_input,
            self.limit_rate_input,
            self.throttled_rate_input,
        ):
            input_widget.textChanged.connect(self.schedule_settings_save)

        self.custom_options_input.textChanged.connect(self.invalidate_js_runtime_cache)

    def schedule_settings_save(self, *_args):
        """Debounce automatic settings writes while the user is editing."""
        if self.is_closing or not self.settings_save_timer:
            return
        self.settings_save_timer.start()

    def get_settings_data(self):
        """Return the settings payload stored on disk."""
        return {
            "destination": self.destination_input.text(),
            "ytdlp_path": self.ytdlp_path_input.text(),
            "ffmpeg_path": self.ffmpeg_path_input.text(),
            "custom_options": self.custom_options_input.text(),
            "limit_rate": self.limit_rate_input.text(),
            "throttled_rate": self.throttled_rate_input.text(),
            "show_auto_captions": self.show_auto_captions_checkbox.isChecked(),
        }

    def save_settings(self, show_feedback=True):
        """Persist current preferences and optionally display save feedback."""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.get_settings_data(), f, indent=2)

            if show_feedback:
                QMessageBox.information(self, "Success", "Settings saved successfully!")
                self.statusBar().showMessage("Settings saved", 3000)
            else:
                self.statusBar().showMessage("Settings auto-saved", 2000)
        except (OSError, TypeError) as e:
            if show_feedback:
                QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")
            else:
                print(f"Error auto-saving settings: {e}")

def main():
    """Create the Qt application and run it with orderly shutdown cleanup."""
    app = QApplication(sys.argv)
    app.setApplicationName("yt-dlp GUI")
    app.setOrganizationName("mme89")
    window = YtDlpGUI()

    def cleanup_window_on_quit():
        """Stop window workers before the Qt application exits."""
        if window is not None:
            window.cleanup_for_exit(interactive=False)

    app.aboutToQuit.connect(cleanup_window_on_quit)
    window.show()
    exit_code = app.exec()

    try:
        window.cleanup_for_exit(interactive=False)
        window.deleteLater()
        app.processEvents()
    except RuntimeError:
        pass

    sys.exit(exit_code)

if __name__ == "__main__":
    main()
