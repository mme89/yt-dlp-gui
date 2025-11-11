#!/usr/bin/env python3
"""
mme89 yt-dlp GUI Wrapper
This application provides an easy-to-use graphical interface for downloading videos without using the command line
"""

import os
import sys
import json
import asyncio
import urllib.request
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit, QTabWidget,
    QGroupBox, QCheckBox, QFileDialog, QMessageBox, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, QThread, Signal, QProcess, QByteArray
from PySide6.QtGui import QFont, QPixmap, QColor, QIcon

class TerminalWindow(QWidget):
    """Separate window for terminal output"""
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("Terminal Output - yt-dlp")
        self.setMinimumSize(800, 500)

        if parent:
            parent_geo = parent.geometry()
            self.setGeometry(
                parent_geo.x() + 50,
                parent_geo.y() + 50,
                800,
                500
            )

        layout = QVBoxLayout(self)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Menlo", 10))
        layout.addWidget(self.output)

        button_layout = QHBoxLayout()
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.output.clear)
        button_layout.addWidget(clear_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def closeEvent(self, event):
        """Handle window close event"""
        self.closed.emit()
        super().closeEvent(event)

    def append(self, text):
        """Append text to the output"""
        self.output.append(text)

    def clear(self):
        """Clear the output"""
        self.output.clear()

class FormatFetcher(QThread):
    """Thread for fetching formats without blocking UI"""
    finished = Signal(dict)
    error = Signal(str)
    output = Signal(str)

    def __init__(self, url, ytdlp_path="yt-dlp"):
        super().__init__()
        self.url = url
        self.ytdlp_path = ytdlp_path

    def run(self):
        try:
            self.output.emit(f"Analyzing video: {self.url}\n")
            self.output.emit(f"Running: {self.ytdlp_path} -J\n")
            self.output.emit("-" * 60 + "\n")

            process = QProcess()
            process.start(self.ytdlp_path, ["-J", self.url])

            self.output.emit("Fetching video information...\n")
            process.waitForFinished(-1)

            if process.exitCode() != 0:
                error_output = process.readAllStandardError().data().decode('utf-8', errors='replace')
                self.output.emit(f"\nError output:\n{error_output}\n")
                self.error.emit("Failed to fetch formats")
                return

            output = process.readAllStandardOutput().data().decode('utf-8')
            self.output.emit("Successfully retrieved video information!\n")
            self.output.emit("-" * 60 + "\n")

            data = json.loads(output)
            self.finished.emit(data)
        except Exception as e:
            self.output.emit(f"\nException: {str(e)}\n")
            self.error.emit(str(e))

class DownloadThread(QThread):
    """Thread for downloading without blocking UI"""
    output = Signal(str)
    progress = Signal(int, str)
    finished_signal = Signal(int)

    def __init__(self, args, url, ytdlp_path="yt-dlp"):
        super().__init__()
        self.args = args
        self.url = url
        self.ytdlp_path = ytdlp_path
        self.process = None
        self._should_stop = False

    def run(self):
        self.process = QProcess()
        self.process.readyReadStandardOutput.connect(self._handle_output)
        self.process.readyReadStandardError.connect(self._handle_output)
        self.process.finished.connect(self._handle_finished)

        self.process.start(self.ytdlp_path, self.args + [self.url])
        self.process.waitForFinished(-1)

    def _handle_output(self):
        if self.process:
            output = self.process.readAllStandardOutput().data().decode('utf-8', errors='replace')
            if output:
                self.output.emit(output)
                self._parse_progress(output)
            error = self.process.readAllStandardError().data().decode('utf-8', errors='replace')
            if error:
                self.output.emit(error)

    def _parse_progress(self, text):
        """Parse yt-dlp output for progress information"""
        import re

        match = re.search(r'\[download\]\s+(\d+\.?\d*)%', text)
        if match:
            percentage = float(match.group(1))

            status_parts = []

            size_match = re.search(r'of\s+([\d.]+\w+)', text)
            if size_match:
                status_parts.append(f"of {size_match.group(1)}")

            speed_match = re.search(r'at\s+([\d.]+\w+/s)', text)
            if speed_match:
                status_parts.append(f"at {speed_match.group(1)}")

            eta_match = re.search(r'ETA\s+([\d:]+)', text)
            if eta_match:
                status_parts.append(f"ETA {eta_match.group(1)}")

            status = " ".join(status_parts) if status_parts else "Downloading..."
            self.progress.emit(int(percentage), status)

        elif '[download] Destination:' in text:
            filename = text.split('Destination:')[-1].strip()
            self.progress.emit(0, f"Starting download: {filename}")
        elif '[download] 100%' in text or 'has already been downloaded' in text:
            self.progress.emit(100, "Download complete!")
        elif '[Merger]' in text or 'Merging formats' in text:
            self.progress.emit(100, "Merging video and audio...")
        elif '[ExtractAudio]' in text:
            self.progress.emit(100, "Extracting audio...")
        elif '[EmbedSubtitle]' in text:
            self.progress.emit(100, "Embedding subtitles...")

    def _handle_finished(self, exit_code):
        self.finished_signal.emit(exit_code)

    def stop(self):
        """Request the download to stop"""
        self._should_stop = True
        if self.process and self.process.state() == QProcess.Running:
            try:
                self.process.terminate()
            except:
                pass

class YtDlpGUI(QMainWindow):
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
        super().__init__()
        self.config_file = Path(__file__).parent / "settings.json"
        self.format_fetcher = None
        self.download_thread = None
        self.video_formats = []
        self.audio_formats = []
        self.subtitles = {}
        self.terminal_window = None
        self.ytdlp_version = None
        self.ffmpeg_version = None
        self.download_queue = []
        self.is_processing_queue = False
        self.current_queue_item = None
        self.format_data = {}
        self.current_playlist_downloads = []

        self.init_ui()
        self.setup_logo()
        self.apply_stylesheet()
        self.load_settings()
        self.check_ytdlp_version()
        self.check_ffmpeg_version()

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
        logo_path = Path(__file__).parent / "assets" / "logo.png"
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))

            logo_pixmap = QPixmap(str(logo_path))
            self.about_logo_label.setPixmap(logo_pixmap.scaled(
                128, 128,
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            ))

    def init_ui(self):
        self.setWindowTitle("mme89 yt-dlp GUI - v1.1.0")
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
        self.thumbnail_label.setStyleSheet(f"border: 1px solid {self.COLORS['border']}; background-color: {self.COLORS['thumbnail_bg']};")
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
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
        self.subtitle_combo = QComboBox()
        self.subtitle_combo.addItem("None", "")
        self.subtitle_combo.addItem("English", "en")
        self.subtitle_combo.addItem("All available", "all")
        subtitle_layout.addWidget(self.subtitle_combo)
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

        layout.addStretch()

        progress_group = QGroupBox("Download Progress")
        progress_layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(20)
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        progress_layout.addWidget(self.status_label)

        self.abort_btn = QPushButton("Abort Download")
        self.abort_btn.clicked.connect(self.abort_download)
        self.abort_btn.setEnabled(False)
        self.abort_btn.setFixedWidth(150)
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
        progress_layout.addWidget(self.abort_btn)

        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)

        self.download_page_status_label = QLabel("Enter a URL and click Analyze")
        self.download_page_status_label.setStyleSheet(f"color: {self.COLORS['text_secondary']};")
        layout.addWidget(self.download_page_status_label)

        self.tabs.addTab(download_widget, "Download")

    def create_playlist_tab(self):
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
        self.playlist_table.setHorizontalHeaderLabels(["", "Status", "Title", "Duration", "Uploader"])
        self.playlist_table.setColumnWidth(0, 30)
        self.playlist_table.setColumnWidth(1, 100)
        self.playlist_table.setColumnWidth(3, 80)
        self.playlist_table.setColumnWidth(4, 250)
        self.playlist_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.playlist_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.playlist_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.playlist_table)

        self.playlist_status_label = QLabel("Enter a playlist URL and click 'Load Playlist'")
        self.playlist_status_label.setStyleSheet(f"color: {self.COLORS['text_secondary']};")
        layout.addWidget(self.playlist_status_label)

        self.tabs.addTab(playlist_widget, "Playlist")

    def create_queue_tab(self):
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
        self.queue_table.setHorizontalHeaderLabels(["#", "Status", "URL", "Title", "Format", "Size"])
        self.queue_table.setColumnWidth(0, 40)
        self.queue_table.setColumnWidth(1, 100)
        self.queue_table.setColumnWidth(4, 100)
        self.queue_table.setColumnWidth(5, 80)
        self.queue_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.queue_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.queue_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.queue_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.queue_table.verticalHeader().setVisible(False)
        layout.addWidget(self.queue_table)

        self.queue_status_label = QLabel("Queue is empty. Add videos from the Download tab.")
        self.queue_status_label.setStyleSheet(f"color: {self.COLORS['text_secondary']};")
        layout.addWidget(self.queue_status_label)

        self.tabs.addTab(queue_widget, "Queue")

    def create_advanced_tab(self):
        advanced_widget = QWidget()
        layout = QVBoxLayout(advanced_widget)

        custom_group = QGroupBox("Custom yt-dlp command")
        custom_layout = QVBoxLayout()
        self.custom_input = QLineEdit()
        self.custom_input.setPlaceholderText("Additional yt-dlp arguments")
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

        dest_label = QLabel("Download destination (leave empty for current directory):")
        layout.addWidget(dest_label)
        layout.addSpacing(3)
        dest_input_layout = QHBoxLayout()
        dest_input_layout.setContentsMargins(0, 0, 0, 0)
        dest_input_layout.setSpacing(6)
        self.destination_input = QLineEdit()
        self.destination_input.setMinimumHeight(20)
        self.destination_input.setPlaceholderText("~/Downloads or /path/to/folder")
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

        max_rate_layout = QVBoxLayout()
        max_rate_layout.setSpacing(0)
        limit_rate_label = QLabel("Maximum download rate:")
        max_rate_layout.addWidget(limit_rate_label)
        max_rate_layout.addSpacing(3)
        self.limit_rate_input = QLineEdit()
        self.limit_rate_input.setMinimumHeight(20)
        self.limit_rate_input.setMaximumWidth(160)
        self.limit_rate_input.setPlaceholderText("e.g., 50K, 4.2M, 1G")
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

        self.show_auto_captions_checkbox = QCheckBox("Show auto-generated captions in subtitle dropdown")
        layout.addWidget(self.show_auto_captions_checkbox)

        layout.addSpacing(10)

        self.save_settings_btn = QPushButton("Save Settings")
        self.save_settings_btn.clicked.connect(self.save_settings)
        layout.addWidget(self.save_settings_btn)

        layout.addStretch()

        info_label = QLabel("Settings auto-saved to: ./settings.json")
        info_label.setStyleSheet(f"color: {self.COLORS['text_secondary']};")
        layout.addWidget(info_label)

        self.tabs.addTab(options_widget, "Options")

    def create_about_tab(self):
        about_widget = QWidget()
        layout = QVBoxLayout(about_widget)
        layout.setAlignment(Qt.AlignTop)

        header_layout = QHBoxLayout()
        header_layout.addStretch()
        
        self.about_logo_label = QLabel()
        self.about_logo_label.setFixedSize(128, 128)
        self.about_logo_label.setScaledContents(True)
        self.about_logo_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(self.about_logo_label)
        
        header_layout.addSpacing(20)
        
        version_widget = QWidget()
        version_layout = QVBoxLayout(version_widget)
        version_layout.setContentsMargins(0, 0, 0, 0)
        version_layout.setAlignment(Qt.AlignVCenter)
        
        app_title = QLabel("mme89 yt-dlp GUI")
        app_title_font = QFont()
        app_title_font.setPointSize(16)
        app_title_font.setBold(True)
        app_title.setFont(app_title_font)
        version_layout.addWidget(app_title)
        
        version_label = QLabel("Version 1.1.0")
        version_label.setStyleSheet(f"color: {self.COLORS['text_secondary']};")
        version_layout.addWidget(version_label)
        
        header_layout.addWidget(version_widget)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        layout.addSpacing(20)

        desc_label = QLabel(
            "A graphical interface for yt-dlp with format selection, "
            "playlist support, and download queue management."
        )
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc_label)

        layout.addSpacing(5)

        github_label = QLabel(
            'GitHub: <a href="https://github.com/mme89/yt-dlp-gui">github.com/mme89/yt-dlp-gui</a>'
        )
        github_label.setAlignment(Qt.AlignCenter)
        github_label.setTextFormat(Qt.RichText)
        github_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        github_label.setOpenExternalLinks(True)
        github_label.setStyleSheet(f"color: {self.COLORS['text_secondary']};")
        layout.addWidget(github_label)

        layout.addSpacing(5)

        license_info = QLabel(
            'Licensed under GNU GPL v3+ - '
            '<a href="https://github.com/mme89/yt-dlp-gui/blob/main/LICENSE">View License</a>'
        )
        license_info.setWordWrap(True)
        license_info.setAlignment(Qt.AlignCenter)
        license_info.setTextFormat(Qt.RichText)
        license_info.setTextInteractionFlags(Qt.TextBrowserInteraction)
        license_info.setOpenExternalLinks(True)
        license_info.setStyleSheet(f"color: {self.COLORS['text_secondary']};")
        layout.addWidget(license_info)

        layout.addSpacing(20)

        powered_by_layout = QHBoxLayout()

        ytdlp_widget = QWidget()
        ytdlp_layout = QVBoxLayout(ytdlp_widget)
        ytdlp_layout.setContentsMargins(0, 0, 10, 0)
        
        ytdlp_label = QLabel("yt-dlp")
        ytdlp_font = QFont()
        ytdlp_font.setPointSize(14)
        ytdlp_font.setBold(True)
        ytdlp_label.setFont(ytdlp_font)
        ytdlp_layout.addWidget(ytdlp_label)

        self.ytdlp_version_label = QLabel("Checking version...")
        self.ytdlp_version_label.setStyleSheet(f"color: {self.COLORS['text_secondary']}; font-style: italic;")
        ytdlp_layout.addWidget(self.ytdlp_version_label)

        ytdlp_layout.addSpacing(10)

        ytdlp_info = QLabel(
            'Core download engine.<br>'
            'Feature-rich command-line<br>'
            'audio/video downloader.<br><br>'
            'GitHub: <a href="https://github.com/yt-dlp/yt-dlp">yt-dlp/yt-dlp</a>'
        )
        ytdlp_info.setWordWrap(True)
        ytdlp_info.setTextFormat(Qt.RichText)
        ytdlp_info.setTextInteractionFlags(Qt.TextBrowserInteraction)
        ytdlp_info.setOpenExternalLinks(True)
        ytdlp_layout.addWidget(ytdlp_info)
        ytdlp_layout.addStretch()
        
        powered_by_layout.addWidget(ytdlp_widget)

        ffmpeg_widget = QWidget()
        ffmpeg_layout = QVBoxLayout(ffmpeg_widget)
        ffmpeg_layout.setContentsMargins(10, 0, 0, 0)
        
        ffmpeg_label = QLabel("FFmpeg")
        ffmpeg_font = QFont()
        ffmpeg_font.setPointSize(14)
        ffmpeg_font.setBold(True)
        ffmpeg_label.setFont(ffmpeg_font)
        ffmpeg_layout.addWidget(ffmpeg_label)

        self.ffmpeg_version_label = QLabel("Checking version...")
        self.ffmpeg_version_label.setStyleSheet(f"color: {self.COLORS['text_secondary']}; font-style: italic;")
        ffmpeg_layout.addWidget(self.ffmpeg_version_label)

        ffmpeg_layout.addSpacing(10)

        ffmpeg_info = QLabel(
            'Used for merging video<br>'
            'and audio streams.<br><br><br>'
            'GitHub: <a href="https://github.com/FFmpeg/FFmpeg">FFmpeg/FFmpeg</a>'
        )
        ffmpeg_info.setWordWrap(True)
        ffmpeg_info.setTextFormat(Qt.RichText)
        ffmpeg_info.setTextInteractionFlags(Qt.TextBrowserInteraction)
        ffmpeg_info.setOpenExternalLinks(True)
        ffmpeg_layout.addWidget(ffmpeg_info)
        ffmpeg_layout.addStretch()
        
        powered_by_layout.addWidget(ffmpeg_widget)
        
        layout.addLayout(powered_by_layout)

        layout.addStretch()
        license_info.setStyleSheet("font-size: 10pt;")
        layout.addWidget(license_info)

        layout.addSpacing(10)

        footer_label = QLabel("© 2025 mme89")
        footer_label.setAlignment(Qt.AlignCenter)
        footer_label.setStyleSheet(f"color: {self.COLORS['text_secondary']}; margin-top: 20px;")
        layout.addWidget(footer_label)

        self.tabs.addTab(about_widget, "About")

    def toggle_terminal_output(self, state):
        """Toggle visibility of terminal output window"""
        if state == 2 or state == Qt.CheckState.Checked:
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
        self.show_terminal_checkbox.setChecked(False)

    def browse_destination(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Download Directory")
        if directory:
            self.destination_input.setText(directory)

    def browse_ytdlp_path(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select yt-dlp Executable")
        if file_path:
            self.ytdlp_path_input.setText(file_path)

    def browse_ffmpeg_path(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select FFmpeg Executable")
        if file_path:
            self.ffmpeg_path_input.setText(file_path)

    def is_valid_url(self, url):
        """Validate if the URL is a valid YouTube/video URL"""
        import re
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
            import subprocess
            if sys.platform == 'win32':
                result = subprocess.run(['where', name], capture_output=True, text=True)
            else:
                result = subprocess.run(['which', name], capture_output=True, text=True)
            
            if result.returncode == 0:
                found_path = result.stdout.strip().split('\n')[0]
                if found_path and os.path.isfile(found_path):
                    return found_path
        except:
            pass
        
        return name

    def get_ytdlp_path(self):
        """Get the yt-dlp path from settings"""
        ytdlp_path = self.ytdlp_path_input.text().strip()
        if ytdlp_path:
            return os.path.expanduser(ytdlp_path)
        return self.find_executable("yt-dlp")

    def check_ytdlp_version(self):
        """Check if yt-dlp is installed and get version"""
        process = None
        try:
            ytdlp_path = self.get_ytdlp_path()
            process = QProcess()
            process.start(ytdlp_path, ["--version"])
            process.waitForFinished(3000)

            if process.exitCode() == 0:
                version = process.readAllStandardOutput().data().decode('utf-8').strip()
                self.ytdlp_version = version
                self.ytdlp_version_label.setText(f"Installed version: {version}")
                self.ytdlp_version_label.setStyleSheet(f"color: {self.COLORS['success']}; font-weight: bold;")
                self.statusBar().showMessage(f"yt-dlp {version} detected", 3000)
            else:
                self.ytdlp_version = "Not found"
                self.ytdlp_version_label.setText("⚠️ yt-dlp not found - Please install it")
                self.ytdlp_version_label.setStyleSheet(f"color: {self.COLORS['error']}; font-weight: bold;")
                
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
                        "• Using pip: pip install yt-dlp\n"
                        "• Using your package manager (e.g., apt, dnf, pacman)\n"
                        "• Or visit: https://github.com/yt-dlp/yt-dlp"
                    )
                
                QMessageBox.warning(self, "yt-dlp Not Found", install_msg)
        except Exception as e:
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
            process = QProcess()
            process.start(ffmpeg_path, ["-version"])
            process.waitForFinished(3000)

            if process.exitCode() == 0:
                output = process.readAllStandardOutput().data().decode('utf-8')
                first_line = output.split('\n')[0]
                if 'version' in first_line:
                    version = first_line.split('version')[1].strip().split()[0]
                    self.ffmpeg_version = version
                    self.ffmpeg_version_label.setText(f"Installed version: {version}")
                    self.ffmpeg_version_label.setStyleSheet(f"color: {self.COLORS['success']}; font-weight: bold;")
                else:
                    self.ffmpeg_version = "Unknown"
                    self.ffmpeg_version_label.setText("Installed (version unknown)")
                    self.ffmpeg_version_label.setStyleSheet(f"color: {self.COLORS['success']};")
            else:
                self.ffmpeg_version = "Not found"
                self.ffmpeg_version_label.setText("⚠️ FFmpeg not found (optional)")
                self.ffmpeg_version_label.setStyleSheet(f"color: {self.COLORS['warning']}; font-style: italic;")
        except Exception as e:
            self.ffmpeg_version = "Error checking version"
            self.ffmpeg_version_label.setText("FFmpeg status unknown")
            self.ffmpeg_version_label.setStyleSheet(f"color: {self.COLORS['text_secondary']}; font-style: italic;")
            print(f"Error checking FFmpeg version: {e}")
        finally:
            if process:
                process.kill()
                process.waitForFinished(500)
                process.deleteLater()

    def fetch_formats(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a URL first!")
            return

        if not self.is_valid_url(url):
            QMessageBox.warning(self, "Invalid URL", "Please enter a valid URL (must start with http:// or https://)")
            return

        self.download_page_status_label.setText("Fetching formats...")
        self.analyze_btn.setEnabled(False)

        if self.terminal_window and self.terminal_window.isVisible():
            self.terminal_window.clear()

        self.format_fetcher = FormatFetcher(url, self.get_ytdlp_path())
        self.format_fetcher.finished.connect(self.on_formats_fetched)
        self.format_fetcher.error.connect(self.on_fetch_error)

        if self.terminal_window and self.terminal_window.isVisible():
            self.format_fetcher.output.connect(lambda text: self.terminal_window.append(text))

        self.format_fetcher.start()

    def on_formats_fetched(self, data):
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

        has_subtitles = bool(self.subtitles or self.automatic_captions)
        
        if has_subtitles:
            self.subtitle_combo.addItem("All available", "all")

            if self.subtitles:
                for lang_code in sorted(self.subtitles.keys()):
                    self.subtitle_combo.addItem(f"{lang_code} (manual)", lang_code)

            if self.automatic_captions:
                for lang_code in sorted(self.automatic_captions.keys()):
                    if lang_code not in self.subtitles:
                        self.subtitle_combo.addItem(f"{lang_code} (auto)", lang_code)
        else:
            self.subtitle_combo.addItem("English (if available)", "en")

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
            try:
                year = upload_date[0:4]
                month = upload_date[4:6]
                day = upload_date[6:8]
                upload_date_str = f"{year}-{month}-{day}"
            except:
                upload_date_str = "Unknown"
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
            if count >= 1_000_000:
                return f"{count / 1_000_000:.1f}M"
            elif count >= 1_000:
                return f"{count / 1_000:.1f}K"
            else:
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
            try:
                with urllib.request.urlopen(thumbnail_url) as response:
                    image_data = response.read()
                    pixmap = QPixmap()
                    pixmap.loadFromData(QByteArray(image_data))
                    self.thumbnail_label.setPixmap(pixmap)
            except Exception as e:
                self.thumbnail_label.setText(f"Failed to load thumbnail")
        else:
            self.thumbnail_label.setText("No thumbnail available")

        self.download_page_status_label.setText(f"Loaded {len(video_formats)} video + {len(audio_formats)} audio formats")
        self.analyze_btn.setEnabled(True)

    def on_fetch_error(self, error):
        QMessageBox.critical(self, "Error", f"Failed to fetch formats: {error}")
        self.download_page_status_label.setText("Error fetching formats")
        self.analyze_btn.setEnabled(True)

    def download_video(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a URL first!")
            return

        if not self.is_valid_url(url):
            QMessageBox.warning(self, "Invalid URL", "Please enter a valid URL (must start with http:// or https://)")
            return

        manual_format = self.format_input.text().strip()

        if manual_format:
            format_id = manual_format
            format_display = manual_format
        else:
            video_id = self.video_combo.currentData()
            audio_id = self.audio_combo.currentData()
            video_text = self.video_combo.currentText()
            audio_text = self.audio_combo.currentText()

            def extract_simple_format(text, is_video=True):
                import re
                if is_video:
                    match = re.search(r'(\d+)x(\d+)', text)
                    if match:
                        height = match.group(2)
                        return f"{height}p"
                    return "video"
                else:
                    match = re.search(r'\b(mp3|m4a|webm|opus|aac|ogg|flac|wav)\b', text, re.IGNORECASE)
                    if match:
                        return match.group(1).lower()
                    return "audio"

            if video_id and audio_id:
                format_id = f"{video_id}+{audio_id}"
                if video_id == "bestvideo":
                    video_part = "best"
                else:
                    video_part = extract_simple_format(video_text, is_video=True)

                if audio_id == "bestaudio":
                    audio_part = "audio"
                else:
                    audio_part = extract_simple_format(audio_text, is_video=False)

                format_display = f"{video_part}+{audio_part}"
            elif video_id:
                format_id = video_id
                if video_id == "bestvideo":
                    format_display = "best"
                else:
                    format_display = extract_simple_format(video_text, is_video=True)
            elif audio_id:
                format_id = audio_id
                if audio_id == "bestaudio":
                    format_display = "audio"
                else:
                    format_display = extract_simple_format(audio_text, is_video=False)
            else:
                format_id = "best"
                format_display = "best"

            if video_id == "none" and audio_id == "none":
                QMessageBox.warning(self, "Error", "Cannot download with both video and audio set to 'none'!")
                return
            elif video_id == "none":
                format_id = audio_id if audio_id else "bestaudio"
                format_display = "audio only"
            elif audio_id == "none":
                format_id = video_id if video_id else "bestvideo"
                format_display = "video only"

        args = ["-f", format_id]

        if video_id == "none" and not manual_format:
            args.extend(["-x", "--audio-format", "mp3"])

        subtitle_lang = self.subtitle_combo.currentData()
        if subtitle_lang:
            args.extend(["--write-subs", "--embed-subs"])
            if subtitle_lang != "all":
                args.extend(["--sub-lang", subtitle_lang])
            else:
                args.append("--all-subs")

        if "+" in format_id:
            args.extend(["--merge-output-format", "mp4"])

        self.run_yt_dlp(args, "download", format_display)

    def calculate_format_size(self, format_id):
        """Calculate total size for the given format ID"""
        if not hasattr(self, 'format_data'):
            return "Unknown"

        total_bytes = 0

        if "+" in format_id:
            parts = format_id.split("+")
            for part in parts:
                if part in self.format_data:
                    filesize = self.format_data[part].get('filesize', 0) or self.format_data[part].get('filesize_approx', 0)
                    if filesize:
                        total_bytes += filesize
        else:
            if format_id in self.format_data:
                total_bytes = self.format_data[format_id].get('filesize', 0) or self.format_data[format_id].get('filesize_approx', 0)

        if total_bytes == 0:
            return "Unknown"
        elif total_bytes > 1024 * 1024 * 1024:
            return f"{total_bytes / (1024**3):.1f} GB"
        elif total_bytes > 1024 * 1024:
            return f"{total_bytes / (1024**2):.0f} MB"
        else:
            return f"{total_bytes / 1024:.0f} KB"

    def add_to_queue(self):
        """Add current video to download queue"""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a URL first!")
            return

        if not self.is_valid_url(url):
            QMessageBox.warning(self, "Invalid URL", "Please enter a valid URL (must start with http:// or https://)")
            return

        manual_format = self.format_input.text().strip()

        if manual_format:
            format_id = manual_format
            format_display = manual_format
        else:
            video_id = self.video_combo.currentData()
            audio_id = self.audio_combo.currentData()
            video_text = self.video_combo.currentText()
            audio_text = self.audio_combo.currentText()

            def extract_simple_format(text, is_video=True):
                import re
                if is_video:
                    match = re.search(r'(\d+)x(\d+)', text)
                    if match:
                        height = match.group(2)
                        return f"{height}p"
                    return "video"
                else:
                    match = re.search(r'\b(mp3|m4a|webm|opus|aac|ogg|flac|wav)\b', text, re.IGNORECASE)
                    if match:
                        return match.group(1).lower()
                    return "audio"

            if video_id and audio_id:
                format_id = f"{video_id}+{audio_id}"
                if video_id == "bestvideo":
                    video_part = "best"
                else:
                    video_part = extract_simple_format(video_text, is_video=True)

                if audio_id == "bestaudio":
                    audio_part = "audio"
                else:
                    audio_part = extract_simple_format(audio_text, is_video=False)

                format_display = f"{video_part}+{audio_part}"
            elif video_id:
                format_id = video_id
                if video_id == "bestvideo":
                    format_display = "best"
                else:
                    format_display = extract_simple_format(video_text, is_video=True)
            elif audio_id:
                format_id = audio_id
                if audio_id == "bestaudio":
                    format_display = "audio"
                else:
                    format_display = extract_simple_format(audio_text, is_video=False)
            else:
                format_id = "best"
                format_display = "best"

            if video_id == "none" and audio_id == "none":
                QMessageBox.warning(self, "Error", "Cannot download with both video and audio set to 'none'!")
                return
            elif video_id == "none":
                format_id = audio_id if audio_id else "bestaudio"
                format_display = "audio only"
            elif audio_id == "none":
                format_id = video_id if video_id else "bestvideo"
                format_display = "video only"

        args = ["-f", format_id]

        if video_id == "none" and not manual_format:
            args.extend(["-x", "--audio-format", "mp3"])

        subtitle_lang = self.subtitle_combo.currentData()
        if subtitle_lang:
            args.extend(["--write-subs", "--embed-subs"])
            if subtitle_lang != "all":
                args.extend(["--sub-lang", subtitle_lang])
            else:
                args.append("--all-subs")

        if "+" in format_id:
            args.extend(["--merge-output-format", "mp4"])

        title = self.title_label.text().replace("Title: ", "") if self.title_label.text() != "Title: -" else "Unknown"

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
        self.start_queue_btn.setEnabled(True)

        QMessageBox.information(self, "Added to Queue", f"Video added to queue!\n\nTotal items in queue: {len(self.download_queue)}")

    def update_queue_table(self):
        """Update the queue table display"""
        self.queue_table.setRowCount(len(self.download_queue))

        for i, item in enumerate(self.download_queue):
            index_item = QTableWidgetItem(str(i + 1))
            index_item.setTextAlignment(Qt.AlignCenter)
            self.queue_table.setItem(i, 0, index_item)

            status_item = QTableWidgetItem(item["status"])
            status_item.setTextAlignment(Qt.AlignCenter)
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
            format_item.setTextAlignment(Qt.AlignCenter)
            self.queue_table.setItem(i, 4, format_item)

            size_display = item.get("size", "Unknown")
            size_item = QTableWidgetItem(size_display)
            size_item.setTextAlignment(Qt.AlignCenter)
            self.queue_table.setItem(i, 5, size_item)

        if len(self.download_queue) == 0:
            self.queue_status_label.setText("Queue is empty. Add videos from the Download tab.")
        else:
            completed = sum(1 for item in self.download_queue if item["status"] == "Completed")
            failed = sum(1 for item in self.download_queue if item["status"] == "Failed")
            pending = sum(1 for item in self.download_queue if item["status"] == "Pending")
            self.queue_status_label.setText(
                f"Total: {len(self.download_queue)} | Pending: {pending} | Completed: {completed} | Failed: {failed}"
            )

    def start_queue_processing(self):
        """Start processing the download queue"""
        if not self.download_queue:
            QMessageBox.warning(self, "Error", "Queue is empty!")
            return

        if self.is_processing_queue:
            QMessageBox.warning(self, "Error", "Queue is already being processed!")
            return

        self.is_processing_queue = True
        self.start_queue_btn.setEnabled(False)
        self.stop_queue_btn.setEnabled(True)
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
            self.start_queue_btn.setEnabled(True)
            self.stop_queue_btn.setEnabled(False)
            self.progress_bar.setVisible(False)
            self.status_label.setText("")
            self.statusBar().showMessage("Queue processing completed!", 5000)
            QMessageBox.information(self, "Queue Complete", "All downloads in the queue have been processed!")
            return

        next_item["status"] = "Downloading"
        self.current_queue_item = next_item
        self.update_queue_table()

        self.run_yt_dlp_queue(next_item["args"], next_item["url"], next_item.get("format_display", ""))

    def run_yt_dlp_queue(self, args, url, format_display=""):
        """Run yt-dlp for queue item"""
        args = args.copy()

        if format_display:
            args.extend(["-o", f"%(title)s [{format_display}].%(ext)s"])
        else:
            args.extend(["-o", "%(title)s [%(format_id)s].%(ext)s"])

        limit_rate = self.limit_rate_input.text().strip()
        if limit_rate:
            args.extend(["--limit-rate", limit_rate])

        throttled_rate = self.throttled_rate_input.text().strip()
        if throttled_rate:
            args.extend(["--throttled-rate", throttled_rate])

        custom_options = self.custom_options_input.text().strip()
        if custom_options:
            import shlex
            try:
                custom_args = shlex.split(custom_options)
                args = custom_args + args
            except ValueError:
                args = custom_options.split() + args

        destination = self.destination_input.text().strip()
        if destination:
            destination = os.path.expanduser(destination)
        else:
            destination = os.path.expanduser("~/Downloads")
        args = ["-P", destination] + args

        ffmpeg_path = self.get_ffmpeg_path()
        if ffmpeg_path and ffmpeg_path != "ffmpeg":
            args = ["--ffmpeg-location", ffmpeg_path] + args

        if self.terminal_window and self.terminal_window.isVisible():
            self.terminal_window.append(f"\n{'='*60}\n")
            self.terminal_window.append(f"Queue: Processing {url}\n")
            self.terminal_window.append(f"Running: yt-dlp {' '.join(args)}\n")
            self.terminal_window.append(f"{'='*60}\n")

        self.download_btn.setEnabled(False)
        self.add_to_queue_btn.setEnabled(False)

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Starting download...")

        self.download_thread = DownloadThread(args, url, self.get_ytdlp_path())
        if self.terminal_window and self.terminal_window.isVisible():
            self.download_thread.output.connect(lambda text: self.terminal_window.append(text))
        self.download_thread.progress.connect(self.update_queue_progress)
        self.download_thread.finished_signal.connect(self.on_queue_download_finished)
        self.download_thread.start()

    def update_queue_progress(self, percentage, status):
        """Update progress bar and status label on Download page"""
        self.progress_bar.setValue(percentage)
        self.status_label.setText(status)

    def on_queue_download_finished(self, exit_code):
        """Handle completion of queue item download"""
        was_aborted = (exit_code == 15 or exit_code == -15)

        if self.current_queue_item:
            if exit_code == 0:
                self.current_queue_item["status"] = "Completed"
            elif was_aborted:
                self.current_queue_item["status"] = "Aborted"
            else:
                self.current_queue_item["status"] = "Failed"
            self.update_queue_table()

        self.download_btn.setEnabled(True)
        self.add_to_queue_btn.setEnabled(True)

        if self.is_processing_queue:
            self.process_next_in_queue()

    def stop_queue_processing(self):
        """Stop processing the queue"""
        if not self.is_processing_queue:
            return

        reply = QMessageBox.question(
            self,
            "Stop Queue",
            "Stop processing the queue?\n\nThe current download will be aborted.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.is_processing_queue = False
            self.start_queue_btn.setEnabled(True)
            self.stop_queue_btn.setEnabled(False)

            self.progress_bar.setVisible(False)
            self.status_label.setText("")

            if self.download_thread and self.download_thread.isRunning():
                self.download_thread.stop()

            if self.current_queue_item and self.current_queue_item["status"] == "Downloading":
                self.current_queue_item["status"] = "Pending"
                self.update_queue_table()

            self.statusBar().showMessage("Queue processing stopped", 3000)

    def clear_queue(self):
        """Clear all items from the queue"""
        if not self.download_queue:
            return

        reply = QMessageBox.question(
            self,
            "Clear Queue",
            f"Remove all {len(self.download_queue)} items from the queue?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
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
            if row < len(self.download_queue) and self.download_queue[row]["status"] == "Downloading":
                QMessageBox.warning(self, "Error", "Cannot remove item that is currently downloading!")
                return

        reply = QMessageBox.question(
            self,
            "Remove Items",
            f"Remove {len(selected_rows)} selected item(s) from queue?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            for row in sorted(selected_rows, reverse=True):
                if row < len(self.download_queue):
                    del self.download_queue[row]

            self.update_queue_table()

            if len(self.download_queue) == 0:
                self.start_queue_btn.setEnabled(False)

    def load_playlist_items(self):
        """Load playlist items and display in table"""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a URL first!")
            return

        if not self.is_valid_url(url):
            QMessageBox.warning(self, "Invalid URL", "Please enter a valid URL (must start with http:// or https://)")
            return

        self.playlist_status_label.setText("Loading playlist...")
        self.list_playlist_btn.setEnabled(False)
        self.playlist_table.setRowCount(0)

        self.playlist_fetcher = FormatFetcher(url, self.get_ytdlp_path())
        self.playlist_fetcher.finished.connect(self.on_playlist_loaded)
        self.playlist_fetcher.error.connect(self.on_playlist_error)

        if self.terminal_window and self.terminal_window.isVisible():
            self.playlist_fetcher.output.connect(lambda text: self.terminal_window.append(text))

        self.playlist_fetcher.start()

    def on_playlist_loaded(self, data):
        """Populate table with playlist items"""
        entries = data.get('entries', [])

        if not entries:
            self.playlist_status_label.setText("No videos found in playlist")
            self.list_playlist_btn.setEnabled(True)
            return

        self.playlist_table.setRowCount(len(entries))

        for i, entry in enumerate(entries):
            checkbox_item = QTableWidgetItem()
            checkbox_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            checkbox_item.setCheckState(Qt.Checked)
            self.playlist_table.setItem(i, 0, checkbox_item)

            status_item = QTableWidgetItem("Pending")
            status_item.setTextAlignment(Qt.AlignCenter)
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
            duration_item.setTextAlignment(Qt.AlignCenter)
            self.playlist_table.setItem(i, 3, duration_item)

            uploader = entry.get('uploader', 'Unknown')
            self.playlist_table.setItem(i, 4, QTableWidgetItem(uploader))

        self.playlist_status_label.setText(f"Loaded {len(entries)} videos. Check videos to download")
        self.list_playlist_btn.setEnabled(True)
        self.download_playlist_btn.setEnabled(True)
        self.check_all_playlist_btn.setEnabled(True)
        self.uncheck_all_playlist_btn.setEnabled(True)

    def on_playlist_error(self, error):
        """Handle playlist loading error"""
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
            if checkbox_item and checkbox_item.checkState() == Qt.Checked:
                checked_rows.append(row)

        if not checked_rows:
            QMessageBox.warning(self, "Error", "Please check at least one video to download!")
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
            format_str = f"bv*[height<={quality}][ext=mp4]+ba[ext=m4a]/b[height<={quality}][ext=mp4] / bv*[height<={quality}]+ba/b[height<={quality}]"

        args = ["-f", format_str, "--merge-output-format", "mp4"]
        args.extend(["-I", items])

        self.current_playlist_downloads = checked_rows

        self.run_yt_dlp(args, "download")

    def check_all_playlist(self):
        """Check all playlist items"""
        for row in range(self.playlist_table.rowCount()):
            checkbox_item = self.playlist_table.item(row, 0)
            if checkbox_item:
                checkbox_item.setCheckState(Qt.Checked)

    def uncheck_all_playlist(self):
        """Uncheck all playlist items"""
        for row in range(self.playlist_table.rowCount()):
            checkbox_item = self.playlist_table.item(row, 0)
            if checkbox_item:
                checkbox_item.setCheckState(Qt.Unchecked)

    def execute_custom(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a URL first!")
            return

        if not self.is_valid_url(url):
            QMessageBox.warning(self, "Invalid URL", "Please enter a valid URL (must start with http:// or https://)")
            return

        custom_args = self.custom_input.text().strip()
        if not custom_args:
            QMessageBox.warning(self, "Error", "Please enter custom arguments!")
            return

        args = custom_args.split()
        self.run_yt_dlp(args, self.advanced_output)

    def get_metadata(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a URL first!")
            return

        self.run_yt_dlp(["--print-json"], self.advanced_output)

    def list_subtitles(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a URL first!")
            return

        self.run_yt_dlp(["--list-subs"], self.advanced_output)

    def run_yt_dlp(self, args, output_type, format_display=""):
        url = self.url_input.text().strip()

        args = args.copy()

        if format_display:
            args.extend(["-o", f"%(title)s [{format_display}].%(ext)s"])

        limit_rate = self.limit_rate_input.text().strip()
        if limit_rate:
            args.extend(["--limit-rate", limit_rate])

        throttled_rate = self.throttled_rate_input.text().strip()
        if throttled_rate:
            args.extend(["--throttled-rate", throttled_rate])

        custom_options = self.custom_options_input.text().strip()
        if custom_options:
            import shlex
            try:
                custom_args = shlex.split(custom_options)
                args = custom_args + args
            except ValueError:
                args = custom_options.split() + args

        destination = self.destination_input.text().strip()
        if destination:
            destination = os.path.expanduser(destination)
        else:
            destination = os.path.expanduser("~/Downloads")
        args = ["-P", destination] + args

        ffmpeg_path = self.get_ffmpeg_path()
        if ffmpeg_path and ffmpeg_path != "ffmpeg":
            args = ["--ffmpeg-location", ffmpeg_path] + args

        is_download = (output_type == "download")

        if self.terminal_window and self.terminal_window.isVisible():
            output_widget = self.terminal_window
            tab_widget = output_type if not is_download else None
        else:
            if is_download:
                output_widget = None
                tab_widget = None
            else:
                output_widget = output_type
                tab_widget = output_type

        if output_widget:
            output_widget.clear()
            output_widget.append(f"Running: yt-dlp {' '.join(args)}\n")
            output_widget.append(f"URL: {url}\n")
            output_widget.append("-" * 60 + "\n")

        if tab_widget and tab_widget != output_widget:
            tab_widget.clear()
            tab_widget.append("═" * 60 + "\n")
            tab_widget.append("📺 Output is being shown in the Terminal Window\n")
            tab_widget.append("═" * 60 + "\n\n")
            tab_widget.append("The detailed yt-dlp output is displayed in the separate terminal window.\n")
            tab_widget.append("You can close the terminal window to see output here instead.\n")

        self.statusBar().showMessage("Running yt-dlp...")
        self.download_btn.setEnabled(False)

        if is_download:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.status_label.setText("Starting download...")
            self.abort_btn.setEnabled(True)

        self.download_thread = DownloadThread(args, url, self.get_ytdlp_path())
        if output_widget:
            self.download_thread.output.connect(lambda text: output_widget.append(text))
        if is_download:
            self.download_thread.progress.connect(self.update_progress)
        self.download_thread.finished_signal.connect(lambda code: self.on_download_finished(code, is_download))
        self.download_thread.start()

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
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.status_label.setText("Aborting download...")
            self.abort_btn.setEnabled(False)

            self.download_thread.stop()

    def on_download_finished(self, exit_code, is_download):
        was_aborted = (exit_code == 15 or exit_code == -15)

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

        self.download_btn.setEnabled(True)

    def closeEvent(self, event):
        """Handle application close - cleanup running processes"""
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.stop()
            self.download_thread.wait(1000)
            if self.download_thread.isRunning():
                self.download_thread.terminate()

        if self.format_fetcher and self.format_fetcher.isRunning():
            self.format_fetcher.terminate()
            self.format_fetcher.wait(500)

        if self.terminal_window:
            self.terminal_window.close()

        event.accept()

    def load_settings(self):
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    settings = json.load(f)

                self.destination_input.setText(settings.get("destination", ""))
                self.ytdlp_path_input.setText(settings.get("ytdlp_path", ""))
                self.ffmpeg_path_input.setText(settings.get("ffmpeg_path", ""))
                self.custom_options_input.setText(settings.get("custom_options", ""))
                self.limit_rate_input.setText(settings.get("limit_rate", ""))
                self.throttled_rate_input.setText(settings.get("throttled_rate", ""))
        except Exception as e:
            print(f"Error loading settings: {e}")

    def save_settings(self):
        try:
            settings = {
                "destination": self.destination_input.text(),
                "ytdlp_path": self.ytdlp_path_input.text(),
                "ffmpeg_path": self.ffmpeg_path_input.text(),
                "custom_options": self.custom_options_input.text(),
                "limit_rate": self.limit_rate_input.text(),
                "throttled_rate": self.throttled_rate_input.text(),
            }

            with open(self.config_file, 'w') as f:
                json.dump(settings, f, indent=2)

            QMessageBox.information(self, "Success", "Settings saved successfully!")
            self.statusBar().showMessage("Settings saved", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("yt-dlp GUI")
    app.setOrganizationName("mme89")
    window = YtDlpGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
