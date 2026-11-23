"""UI tab builders and stylesheet definition for the main window."""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QRegularExpression, Qt
from PySide6.QtGui import QFontDatabase, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from .compatibility import RECOMMENDED_YTDLP_VERSION
from .version import APP_VERSION


class TabsMixin:
    """Mixin building the stylesheet and all six feature tabs of YtDlpGUI."""

    COLORS: dict[str, str]
    tabs: Any
    config_file: Any

    if TYPE_CHECKING:
        setStyleSheet: Callable[[str], None]
        update_subtitle_option_states: Callable[..., Any]
        download_video: Callable[..., Any]
        add_to_queue: Callable[..., Any]
        abort_download: Callable[..., Any]
        load_playlist_items: Callable[..., Any]
        cancel_playlist_load: Callable[..., Any]
        download_playlist: Callable[..., Any]
        check_all_playlist: Callable[..., Any]
        uncheck_all_playlist: Callable[..., Any]
        start_queue_processing: Callable[..., Any]
        stop_queue_processing: Callable[..., Any]
        clear_queue: Callable[..., Any]
        remove_selected_from_queue: Callable[..., Any]
        execute_custom: Callable[..., Any]
        get_metadata: Callable[..., Any]
        list_subtitles: Callable[..., Any]
        cancel_advanced_command: Callable[..., Any]
        browse_destination: Callable[..., Any]
        browse_ytdlp_path: Callable[..., Any]
        browse_ffmpeg_path: Callable[..., Any]
        toggle_terminal_output: Callable[..., Any]
        on_show_auto_captions_changed: Callable[..., Any]
        save_settings: Callable[..., Any]
        check_for_updates: Callable[..., Any]

    def apply_stylesheet(self):
        """Apply consistent stylesheet across all platforms."""
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

            QTextEdit, QPlainTextEdit {{
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

        output_fmt_group = QGroupBox("Output Format")
        output_fmt_layout = QHBoxLayout()
        output_fmt_layout.addWidget(QLabel("Video container:"))
        self.video_container_combo = QComboBox()
        self.video_container_combo.addItem("MP4", "mp4")
        self.video_container_combo.addItem("MKV", "mkv")
        self.video_container_combo.addItem("Original (auto)", "original")
        output_fmt_layout.addWidget(self.video_container_combo, 1)

        output_fmt_layout.addSpacing(16)
        output_fmt_layout.addWidget(QLabel("Audio-only format:"))
        self.audio_format_combo = QComboBox()
        self.audio_format_combo.addItem("Original (no re-encode)", "original")
        self.audio_format_combo.addItem("MP3", "mp3")
        self.audio_format_combo.addItem("M4A", "m4a")
        self.audio_format_combo.addItem("Opus", "opus")
        output_fmt_layout.addWidget(self.audio_format_combo, 1)
        output_fmt_group.setLayout(output_fmt_layout)
        layout.addWidget(output_fmt_group)

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
        self.cancel_playlist_btn = QPushButton("Cancel")
        self.cancel_playlist_btn.setEnabled(False)
        self.cancel_playlist_btn.clicked.connect(self.cancel_playlist_load)
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
        btn_layout.addWidget(self.cancel_playlist_btn)
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
        self.cancel_advanced_btn = QPushButton("Cancel")
        self.cancel_advanced_btn.setEnabled(False)
        self.cancel_advanced_btn.clicked.connect(self.cancel_advanced_command)
        btn_layout.addWidget(self.execute_custom_btn)
        btn_layout.addWidget(self.metadata_btn)
        btn_layout.addWidget(self.list_subs_btn)
        btn_layout.addWidget(self.cancel_advanced_btn)
        layout.addLayout(btn_layout)

        self.advanced_output = QPlainTextEdit()
        self.advanced_output.setReadOnly(True)
        self.advanced_output.setMaximumBlockCount(5000)
        fixed_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        fixed_font.setPointSize(10)
        self.advanced_output.setFont(fixed_font)
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
            options_widget,
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
        """Build a compact About page that scrolls when display scaling needs more space."""
        about_widget = QWidget()
        about_widget.setObjectName("aboutContent")
        about_widget.setStyleSheet(
            'QLabel { font-size: 13px; }'
            'QLabel#aboutTitle { font-size: 18px; font-weight: bold; }'
            'QLabel[aboutHeading="true"] { font-size: 14px; font-weight: bold; }'
        )
        layout = QVBoxLayout(about_widget)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)
        self.about_logo_label = QLabel()
        self.about_logo_label.setFixedSize(80, 80)
        self.about_logo_label.setScaledContents(True)
        self.about_logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.about_logo_label)

        version_layout = QVBoxLayout()
        version_layout.setSpacing(4)
        version_layout.addStretch()
        app_title = QLabel("mme89 yt-dlp GUI")
        app_title.setObjectName("aboutTitle")
        version_layout.addWidget(app_title)
        version_label = QLabel(f"Version {APP_VERSION}")
        version_label.setStyleSheet(f"color: {self.COLORS['text_secondary']};")
        version_layout.addWidget(version_label)
        version_layout.addStretch()
        header_layout.addLayout(version_layout, 1)

        update_layout = QVBoxLayout()
        update_layout.setSpacing(6)
        update_layout.addStretch()
        self.check_updates_button = QPushButton("Check for Updates")
        self.check_updates_button.clicked.connect(self.check_for_updates)
        update_layout.addWidget(self.check_updates_button, 0, Qt.AlignmentFlag.AlignRight)
        self.update_status_label = QLabel("Updates are checked automatically.")
        self.configure_about_status_label(self.update_status_label)
        self.update_status_label.setMaximumWidth(360)
        self.update_status_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.update_status_label.setTextFormat(Qt.TextFormat.RichText)
        self.update_status_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        self.update_status_label.setOpenExternalLinks(True)
        self.update_status_label.setStyleSheet(f"color: {self.COLORS['text_secondary']};")
        update_layout.addWidget(self.update_status_label)
        update_layout.addStretch()
        header_layout.addLayout(update_layout, 1)
        layout.addLayout(header_layout)

        description = QLabel(
            "A graphical interface for yt-dlp with format selection, "
            "playlist support, and download queue management."
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        project_links = QLabel(
            '<a href="https://github.com/mme89/yt-dlp-gui">GitHub</a>'
            ' · Licensed under GNU GPL v3+ · '
            '<a href="https://github.com/mme89/yt-dlp-gui/blob/main/LICENSE">View license</a>'
        )
        project_links.setWordWrap(True)
        project_links.setOpenExternalLinks(True)
        layout.addWidget(project_links)

        dependencies = QGridLayout()
        dependencies.setHorizontalSpacing(24)
        dependencies.setVerticalSpacing(10)
        dependency_details = (
            (
                "yt-dlp", "ytdlp_version_label", "Checking version…",
                f"Core download engine. Recommended: {RECOMMENDED_YTDLP_VERSION} or newer."
                "<br><br>Python installs require Python 3.11+. "
                "Windows binaries require Windows 10+.",
                '<a href="https://github.com/yt-dlp/yt-dlp">yt-dlp on GitHub</a>',
            ),
            (
                "JS Runtime", "js_runtime_version_label", "Checking runtime…",
                "Used for YouTube JavaScript extraction. "
                "Prefer Deno 2.3+ or Node.js 22+."
                "<br><br>QuickJS is also supported. "
                "Bun is deprecated (1.2.11–1.3.14 only).",
                '<a href="https://github.com/yt-dlp/yt-dlp/wiki/EJS">Runtime setup guide</a>',
            ),
            (
                "yt-dlp-ejs", "ytdlp_ejs_status_label", "Managed by yt-dlp (not verified)",
                "Challenge solver scripts for full YouTube support. "
                "Included in official yt-dlp binaries."
                "<br><br>For pip installs: pip install -U &quot;yt-dlp[default]&quot; "
                "in the environment containing yt-dlp.",
                '<a href="https://github.com/yt-dlp/ejs">EJS on GitHub</a>',
            ),
            (
                "FFmpeg", "ffmpeg_version_label", "Checking version…",
                "Used for merging video and audio streams.",
                '<a href="https://github.com/FFmpeg/FFmpeg">FFmpeg on GitHub</a>',
            ),
        )
        for column, (title, status_name, initial_status, details, link) in enumerate(
            dependency_details
        ):
            dependencies.setColumnStretch(column, 1)
            heading = QLabel(title)
            heading.setProperty("aboutHeading", True)
            dependencies.addWidget(heading, 0, column)
            status = QLabel(initial_status)
            self.configure_about_status_label(status)
            status.setTextFormat(Qt.TextFormat.PlainText)
            status.setStyleSheet(f"color: {self.COLORS['text_secondary']};")
            setattr(self, status_name, status)
            dependencies.addWidget(status, 1, column, Qt.AlignmentFlag.AlignTop)
            info = QLabel(details)
            self.configure_about_status_label(info)
            info.setTextFormat(Qt.TextFormat.RichText)
            dependencies.addWidget(info, 2, column, Qt.AlignmentFlag.AlignTop)
            docs_link = QLabel(link)
            docs_link.setWordWrap(True)
            docs_link.setOpenExternalLinks(True)
            dependencies.addWidget(docs_link, 3, column, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(dependencies)
        layout.addStretch()

        footer = QLabel("© 2025-2026 mme89")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet(f"color: {self.COLORS['text_secondary']};")
        layout.addWidget(footer)

        self.about_scroll_area = QScrollArea()
        self.about_scroll_area.setObjectName("aboutScrollArea")
        self.about_scroll_area.setWidgetResizable(True)
        self.about_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.about_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.about_scroll_area.setWidget(about_widget)
        self.tabs.addTab(self.about_scroll_area, "About")
