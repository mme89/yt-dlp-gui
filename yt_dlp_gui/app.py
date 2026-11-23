#!/usr/bin/env python3
"""
mme89 yt-dlp GUI Wrapper
This application provides an easy-to-use graphical interface for downloading videos
without using the command line.
"""

# pylint: disable=too-many-lines
from collections import deque
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import Qt, QStandardPaths, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPixmap, QTextCursor
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .commands import CommandMixin, build_output_template, split_cli_args
from .formatters import extract_video_metadata, format_duration, parse_video_formats
from .probes import ProbeMixin
from .queue_controller import QueueMixin
from .tabs import TabsMixin
from .terminal_window import TerminalWindow
from .updates import UpdateChecker
from .version import APP_VERSION
from .workers import DownloadThread, FormatFetcher


APP_ROOT = Path(__file__).resolve().parent.parent
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", APP_ROOT))
EXECUTABLE_DIR = (
    Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else APP_ROOT
)


class YtDlpGUI(ProbeMixin, CommandMixin, TabsMixin, QueueMixin, QMainWindow):
    """Main window coordinating downloads, settings, and background workers."""

    COLORS = {
        "background": "#f5f5f5",
        "surface": "#ffffff",
        "primary": "#2196F3",
        "primary_dark": "#1976D2",
        "primary_light": "#BBDEFB",
        "text_primary": "#212121",
        "text_secondary": "#757575",
        "text_disabled": "#BDBDBD",
        "success": "#4CAF50",
        "error": "#F44336",
        "warning": "#FF9800",
        "info": "#2196F3",
        "border": "#E0E0E0",
        "border_focus": "#2196F3",
        "hover": "#E3F2FD",
        "pressed": "#BBDEFB",
        "thumbnail_bg": "#EEEEEE",
        "input_bg": "#FFFFFF",
        "button_bg": "#FAFAFA",
        "button_text": "#212121",
    }

    def __init__(self):
        """Initialize application state, build the interface, and schedule update checks."""
        super().__init__()
        self.legacy_config_file = EXECUTABLE_DIR / "settings.json"
        self.config_file = self.get_config_file_path()
        self.format_fetcher = None
        self.playlist_fetcher = None
        self.download_thread = None
        self._worker_threads = set()
        self._probe_workers = {}
        self.analyzed_url = None
        self.loaded_playlist_url = None
        self.video_formats = []
        self.audio_formats = []
        self.subtitles = {}
        self.automatic_captions = {}
        self.terminal_window = None
        self._terminal_buffer = deque(maxlen=2000)
        self.ytdlp_version = None
        self.ffmpeg_version = None
        self.js_runtime_version = None
        self.js_runtime_info = None
        self.js_runtime_cache_dirty = True
        self._dependency_status_dirty = False
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
        self.check_ytdlp_version(async_mode=True)
        self.check_ffmpeg_version(async_mode=True)
        self.check_js_runtime_version(async_mode=True)
        self.check_ytdlp_ejs_status()
        self.update_startup_timer = QTimer(self)
        self.update_startup_timer.setSingleShot(True)
        self.update_startup_timer.timeout.connect(self.check_for_updates)
        self.update_startup_timer.start(1500)
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(7 * 24 * 60 * 60 * 1000)
        self.update_timer.timeout.connect(self.check_for_updates)
        self.update_timer.start()

    def setup_logo(self):
        """Setup window icon and logo display."""
        logo_path = RESOURCE_ROOT / "assets" / "logo.png"
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))

            logo_pixmap = QPixmap(str(logo_path))
            self.about_logo_label.setPixmap(
                logo_pixmap.scaled(
                    self.about_logo_label.width(),
                    self.about_logo_label.height(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

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
        self.cancel_analyze_btn = QPushButton("Cancel")
        self.cancel_analyze_btn.setEnabled(False)
        self.cancel_analyze_btn.clicked.connect(self.cancel_analyze)
        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.analyze_btn)
        url_layout.addWidget(self.cancel_analyze_btn)
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
        for label in (
            self.title_label,
            self.duration_label,
            self.uploader_label,
            self.upload_date_label,
            self.views_label,
            self.likes_label,
        ):
            info_layout.addWidget(label)
        info_layout.addStretch()
        thumbnail_info_layout.addWidget(info_widget)

        url_main_layout.addLayout(thumbnail_info_layout)
        url_group.setLayout(url_main_layout)
        main_layout.addWidget(url_group)

        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.on_tab_changed)
        main_layout.addWidget(self.tabs)

        self.create_download_tab()
        self.create_queue_tab()
        self.create_playlist_tab()
        self.create_advanced_tab()
        self.create_options_tab()
        self.create_about_tab()

        self.statusBar().showMessage("Ready")

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
                if notification.standardButton(button) == QMessageBox.StandardButton.Open
                else None
            )
            notification.finished.connect(self.on_update_notification_closed)
            self.update_notification = notification
            notification.setModal(False)
            notification.show()

    def on_update_notification_closed(self, _result):
        """Release the reference to the dismissed update notification."""
        self.update_notification = None

    def append_terminal_output(self, text):
        """Buffer yt-dlp output and stream it live to the terminal window if visible."""
        if self.is_closing:
            return
        self._terminal_buffer.append(text)
        if self.terminal_window and self.terminal_window.isVisible():
            self.terminal_window.append(text)

    def clear_terminal_output(self):
        """Clear buffered terminal output and the visible terminal window."""
        self._terminal_buffer.clear()
        if self.terminal_window:
            self.terminal_window.output.clear()

    def on_terminal_cleared(self):
        """Keep the live terminal buffer in sync when the user clicks Clear."""
        self._terminal_buffer.clear()

    def toggle_terminal_output(self, state):
        """Toggle visibility of terminal output window."""
        if Qt.CheckState(state) == Qt.CheckState.Checked:
            if not self.terminal_window:
                self.terminal_window = TerminalWindow(self)
                self.terminal_window.closed.connect(self.on_terminal_closed)
                self.terminal_window.cleared.connect(self.on_terminal_cleared)
            self.terminal_window.set_text("".join(self._terminal_buffer))
            self.terminal_window.show()
            self.terminal_window.raise_()
            self.terminal_window.activateWindow()
        else:
            if self.terminal_window:
                self.terminal_window.hide()

    def on_terminal_closed(self):
        """Handle terminal window being closed."""
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
        """Validate if the URL is a valid HTTP/HTTPS URL (including long TLDs and IPv6)."""
        if not url or any(ch.isspace() for ch in url):
            return False

        try:
            parsed = urlparse(url)
            _ = parsed.port
        except ValueError:
            return False

        if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
            return False

        host = parsed.hostname
        if host == "localhost" or ":" in host:
            return True
        return "." in host and not host.startswith(".") and not host.endswith("..")

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

    def fetch_formats(self):
        """Validate the URL and start fetching video metadata in the background."""
        if self.format_fetcher and self.format_fetcher.isRunning():
            self.download_page_status_label.setText("Already fetching formats...")
            return

        url = self.get_validated_url()
        if url is None:
            return

        self.download_page_status_label.setText("Fetching formats...")
        self.analyze_btn.setEnabled(False)
        self.cancel_analyze_btn.setEnabled(True)

        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.status_label.setText("")

        self.clear_terminal_output()

        custom_args = self.get_custom_options_args()
        fetch_op_args = (
            ["-J"]
            if "--yes-playlist" in custom_args or "--no-playlist" in custom_args
            else ["--no-playlist", "-J"]
        )
        args_without_url = self.build_ytdlp_args(fetch_op_args)
        if args_without_url is None:
            self.download_page_status_label.setText("Ready")
            self.analyze_btn.setEnabled(True)
            self.cancel_analyze_btn.setEnabled(False)
            return

        self.analyzed_url = None
        self.format_fetcher = FormatFetcher(
            url,
            self.get_ytdlp_path(),
            args_without_url=args_without_url,
        )
        self.track_worker_thread(self.format_fetcher)
        self.format_fetcher.finished.connect(self.on_formats_fetched)
        self.format_fetcher.error.connect(self.on_fetch_error)
        self.format_fetcher.output.connect(self.append_terminal_output)

        self.format_fetcher.start()

    def cancel_analyze(self):
        """Cancel an in-progress metadata/format analysis."""
        fetcher = self.format_fetcher
        if not fetcher or not fetcher.isRunning():
            return
        self.cancel_analyze_btn.setEnabled(False)
        self.download_page_status_label.setText("Cancelling analysis...")
        fetcher.stop()

    def on_formats_fetched(self, data):
        """Populate format selectors and video details from the active fetcher."""
        fetcher = self.sender()
        if fetcher is not self.format_fetcher:
            return

        self.format_fetcher = None
        if self.is_closing:
            return
        self.analyzed_url = getattr(fetcher, "url", None)

        self.subtitles = data.get("subtitles") or {}
        self.automatic_captions = data.get("automatic_captions") or {}

        video_formats, audio_formats, self.format_data = parse_video_formats(data.get("formats"))

        self.video_combo.clear()
        self.video_combo.addItem("Best video", "bestvideo")
        for label, fid, _ in video_formats:
            self.video_combo.addItem(label, fid)
        self.video_combo.addItem("No video (audio only)", "none")

        self.audio_combo.clear()
        self.audio_combo.addItem("Best audio", "bestaudio")
        for label, fid, _ in audio_formats:
            self.audio_combo.addItem(label, fid)
        self.audio_combo.addItem("No audio (video only)", "none")

        self.populate_subtitle_dropdown()

        metadata = extract_video_metadata(data)
        self.title_label.setText(f"Title: {metadata['title']}")
        self.duration_label.setText(f"Duration: {metadata['duration']}")
        self.uploader_label.setText(f"Uploader: {metadata['uploader']}")
        self.upload_date_label.setText(f"Uploaded: {metadata['upload_date']}")
        self.views_label.setText(f"Views: {metadata['views']}")
        self.likes_label.setText(f"Likes: {metadata['likes']}")

        if metadata["thumbnail"]:
            self.load_thumbnail(metadata["thumbnail"])
        else:
            self._cancel_active_thumbnail_reply()
            self.thumbnail_label.clear()
            self.thumbnail_label.setText("No thumbnail available")

        self.download_page_status_label.setText(
            f"Loaded {len(video_formats)} video + {len(audio_formats)} audio formats"
        )
        self.analyze_btn.setEnabled(True)
        self.cancel_analyze_btn.setEnabled(False)

    def on_fetch_error(self, error):
        """Restore download controls and report an active metadata fetch failure."""
        fetcher = self.sender()
        if fetcher is not self.format_fetcher:
            return

        self.format_fetcher = None
        if self.is_closing:
            return
        self.analyzed_url = None
        self.cancel_analyze_btn.setEnabled(False)
        self.analyze_btn.setEnabled(True)

        if getattr(fetcher, "stop_requested", False):
            self.download_page_status_label.setText("Analysis cancelled")
            return

        QMessageBox.critical(self, "Error", f"Failed to fetch formats: {error}")
        self.download_page_status_label.setText("Error fetching formats")

    def populate_subtitle_dropdown(self, *, preserve_selection=False):
        """Populate the subtitle dropdown from fetched manual and auto captions."""
        current_selection = self.subtitle_combo.currentData() if preserve_selection else None

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

        if preserve_selection and current_selection is not None:
            for i in range(self.subtitle_combo.count()):
                if self.subtitle_combo.itemData(i) == current_selection:
                    self.subtitle_combo.setCurrentIndex(i)
                    break

        self.update_subtitle_option_states()

    def refresh_subtitle_dropdown(self):
        """Refresh subtitle dropdown when auto-captions checkbox is toggled."""
        if not hasattr(self, "subtitles") or not hasattr(self, "automatic_captions"):
            return
        self.populate_subtitle_dropdown(preserve_selection=True)

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
            return False

        return (
            subtitle_lang in self.automatic_captions
            and self.subtitle_combo.currentText().endswith("(auto)")
        )

    def add_subtitle_args(self, args, *, embed=True):
        """Append subtitle-related yt-dlp arguments based on the current UI state."""
        subtitle_lang = self.subtitle_combo.currentData()
        if not subtitle_lang:
            return

        includes_auto = self.subtitle_selection_includes_auto_captions(subtitle_lang)
        keep_files = self.keep_subtitle_files_checkbox.isChecked()

        if embed:
            args.append("--embed-subs")
            if includes_auto:
                args.append("--write-auto-subs")
                if not keep_files:
                    args.extend(["--compat-options", "no-keep-subs"])
            if keep_files:
                args.append("--write-subs")
        else:
            args.append("--write-auto-subs" if includes_auto else "--write-subs")

        if subtitle_lang != "all":
            args.extend(["--sub-langs", subtitle_lang])
        else:
            args.extend(["--sub-langs", self.get_all_subtitle_langs_value()])

    def _cancel_active_thumbnail_reply(self):
        """Abort and detach any in-flight thumbnail network reply."""
        reply = self.active_thumbnail_reply
        self.active_thumbnail_reply = None
        if reply is not None:
            try:
                reply.finished.disconnect(self.on_thumbnail_loaded)
            except (RuntimeError, TypeError):
                pass
            reply.abort()
            reply.deleteLater()

    def load_thumbnail(self, url):
        """Load thumbnail using QtNetwork for better PyInstaller compatibility."""
        try:
            self._cancel_active_thumbnail_reply()
            request = QNetworkRequest(QUrl(url))
            request.setAttribute(
                QNetworkRequest.Attribute.RedirectPolicyAttribute,
                QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy,
            )
            reply = self.network_manager.get(request)
            self.active_thumbnail_reply = reply
            reply.finished.connect(self.on_thumbnail_loaded)
        except (RuntimeError, TypeError, ValueError):
            self.thumbnail_label.clear()
            self.thumbnail_label.setText("Failed to load thumbnail")

    def on_thumbnail_loaded(self):
        """Handle thumbnail download completion."""
        reply = self.sender()
        if reply is not self.active_thumbnail_reply:
            if reply is not None:
                reply.deleteLater()
            return

        self.active_thumbnail_reply = None
        try:
            if self.is_closing:
                return
            if reply.error() == QNetworkReply.NetworkError.NoError:
                image_data = reply.readAll()
                pixmap = QPixmap()
                if pixmap.loadFromData(image_data):
                    self.thumbnail_label.setPixmap(pixmap)
                else:
                    self.thumbnail_label.clear()
                    self.thumbnail_label.setText("Failed to load thumbnail")
            else:
                error_string = reply.errorString()
                print(f"Network error loading thumbnail: {error_string}")
                self.thumbnail_label.clear()
                self.thumbnail_label.setText("Failed to load thumbnail")
        except (RuntimeError, TypeError, ValueError) as e:
            print(f"Exception loading thumbnail: {e}")
            self.thumbnail_label.clear()
            self.thumbnail_label.setText("Failed to load thumbnail")
        finally:
            reply.deleteLater()

    def append_worker_output(self, output_widget, text):
        """Append worker output to a caller-selected widget without double-spacing."""
        if self.is_closing or not output_widget:
            return

        if isinstance(output_widget, QPlainTextEdit):
            cursor = output_widget.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(text)
            output_widget.setTextCursor(cursor)
            output_widget.ensureCursorVisible()
        else:
            output_widget.append(text)

    def connect_worker_output(self, worker, output_widget):
        """Route a worker's text output signal to a specific widget."""
        if output_widget:
            worker.output.connect(
                lambda text, widget=output_widget: self.append_worker_output(widget, text)
            )

    def track_worker_thread(self, thread):
        """Keep a QThread alive until Qt's finished signal fires, then schedule deletion."""
        self._worker_threads.add(thread)
        thread.finished.connect(lambda t=thread: self._release_worker_thread(t))

    def _release_worker_thread(self, thread):
        """Release a completed QThread once its run() method has exited."""
        self._worker_threads.discard(thread)
        thread.deleteLater()

    def on_download_thread_finished(self, exit_code):
        """Dispatch normal download completion based on the sending thread."""
        thread = self.sender()
        if thread is not self.download_thread:
            return
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
        has_pending_queue = any(item["status"] == "Pending" for item in self.download_queue)
        playlist_downloading = bool(
            self.current_playlist_downloads and self.is_ytdlp_command_running()
        )

        self.download_btn.setEnabled(can_start)
        self.add_to_queue_btn.setEnabled(True)
        self.execute_custom_btn.setEnabled(can_start)
        self.metadata_btn.setEnabled(can_start)
        self.list_subs_btn.setEnabled(can_start)
        self.cancel_advanced_btn.setEnabled(
            bool(
                self.download_thread
                and self.download_thread.isRunning()
                and not getattr(self.download_thread, "is_download", True)
            )
        )
        self.list_playlist_btn.setEnabled(not playlist_downloading and not self.playlist_fetcher)
        self.download_playlist_btn.setEnabled(can_start and self.playlist_table.rowCount() > 0)
        self.start_queue_btn.setEnabled(can_start and has_pending_queue)
        self.stop_queue_btn.setEnabled(self.is_processing_queue)
        self.clear_queue_btn.setEnabled(not self.is_processing_queue)

    def download_video(self):
        """Validate the selected video and start downloading the chosen formats."""
        if self.get_validated_url() is None:
            return

        selection = self.build_selected_download_args()
        if not selection:
            return

        args, _, format_display = selection
        self.run_yt_dlp(args, is_download=True, format_display=format_display)

    def load_playlist_items(self):
        """Load playlist items and display in table."""
        if self.playlist_fetcher and self.playlist_fetcher.isRunning():
            self.playlist_status_label.setText("Already loading playlist...")
            return

        if self.current_playlist_downloads and self.is_ytdlp_command_running():
            QMessageBox.warning(
                self,
                "Playlist Downloading",
                "Cannot load a new playlist while a playlist download is in progress.",
            )
            return

        url = self.get_validated_url()
        if url is None:
            return

        self.playlist_status_label.setText("Loading playlist...")
        self.list_playlist_btn.setEnabled(False)
        self.cancel_playlist_btn.setEnabled(True)
        self.download_playlist_btn.setEnabled(False)
        self.check_all_playlist_btn.setEnabled(False)
        self.uncheck_all_playlist_btn.setEnabled(False)
        self.playlist_table.setRowCount(0)
        self.loaded_playlist_url = None

        args_without_url = self.build_ytdlp_args(["--flat-playlist", "-J"])
        if args_without_url is None:
            self.playlist_status_label.setText("Ready")
            self.list_playlist_btn.setEnabled(True)
            self.cancel_playlist_btn.setEnabled(False)
            return

        self.playlist_fetcher = FormatFetcher(
            url,
            self.get_ytdlp_path(),
            args_without_url=args_without_url,
        )
        self.track_worker_thread(self.playlist_fetcher)
        self.playlist_fetcher.finished.connect(self.on_playlist_loaded)
        self.playlist_fetcher.error.connect(self.on_playlist_error)
        self.playlist_fetcher.output.connect(self.append_terminal_output)

        self.playlist_fetcher.start()

    def cancel_playlist_load(self):
        """Cancel an in-progress playlist load."""
        fetcher = self.playlist_fetcher
        if not fetcher or not fetcher.isRunning():
            return
        self.cancel_playlist_btn.setEnabled(False)
        self.playlist_status_label.setText("Cancelling playlist load...")
        fetcher.stop()

    def on_playlist_loaded(self, data):
        """Populate table with playlist items."""
        fetcher = self.sender()
        if fetcher is not self.playlist_fetcher:
            return

        self.playlist_fetcher = None
        if self.is_closing:
            return

        entries = [entry for entry in (data.get("entries") or []) if isinstance(entry, dict)]

        if not entries:
            self.loaded_playlist_url = None
            self.playlist_status_label.setText("No videos found in playlist")
            self.list_playlist_btn.setEnabled(True)
            self.cancel_playlist_btn.setEnabled(False)
            self.download_playlist_btn.setEnabled(False)
            self.check_all_playlist_btn.setEnabled(False)
            self.uncheck_all_playlist_btn.setEnabled(False)
            return

        self.loaded_playlist_url = getattr(fetcher, "url", None)
        self.playlist_table.setRowCount(len(entries))

        for i, entry in enumerate(entries):
            checkbox_item = QTableWidgetItem()
            checkbox_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            checkbox_item.setCheckState(Qt.CheckState.Checked)
            self.playlist_table.setItem(i, 0, checkbox_item)

            status_item = QTableWidgetItem("Pending")
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setForeground(QColor(self.COLORS["text_secondary"]))
            self.playlist_table.setItem(i, 1, status_item)

            self.playlist_table.setItem(i, 2, QTableWidgetItem(entry.get("title") or "Unknown"))

            duration_item = QTableWidgetItem(format_duration(entry.get("duration") or 0))
            duration_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.playlist_table.setItem(i, 3, duration_item)

            self.playlist_table.setItem(i, 4, QTableWidgetItem(entry.get("uploader") or "Unknown"))

        self.playlist_status_label.setText(
            f"Loaded {len(entries)} videos. Check videos to download"
        )
        self.list_playlist_btn.setEnabled(True)
        self.cancel_playlist_btn.setEnabled(False)
        self.download_playlist_btn.setEnabled(
            not self.is_ytdlp_command_running() and not self.is_processing_queue
        )
        self.check_all_playlist_btn.setEnabled(True)
        self.uncheck_all_playlist_btn.setEnabled(True)

    def on_playlist_error(self, error):
        """Handle playlist loading error."""
        fetcher = self.sender()
        if fetcher is not self.playlist_fetcher:
            return

        self.playlist_fetcher = None
        if self.is_closing:
            return

        self.loaded_playlist_url = None
        self.list_playlist_btn.setEnabled(True)
        self.cancel_playlist_btn.setEnabled(False)
        self.download_playlist_btn.setEnabled(False)
        self.check_all_playlist_btn.setEnabled(False)
        self.uncheck_all_playlist_btn.setEnabled(False)
        if getattr(fetcher, "stop_requested", False):
            self.playlist_status_label.setText("Playlist load cancelled")
            return
        self.playlist_status_label.setText(f"Error: {error}")
        QMessageBox.critical(self, "Error", f"Failed to load playlist: {error}")

    def download_playlist(self):
        """Download checked playlist items."""
        url = self.loaded_playlist_url or self.url_input.text().strip()
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

        checked_rows = []
        for row in range(self.playlist_table.rowCount()):
            checkbox_item = self.playlist_table.item(row, 0)
            if checkbox_item and checkbox_item.checkState() == Qt.CheckState.Checked:
                checked_rows.append(row)

        if not checked_rows:
            QMessageBox.warning(self, "Error", "Please check at least one video to download!")
            return

        if self.is_processing_queue or self.warn_if_ytdlp_command_running():
            return

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

        args = ["-f", format_str, "--merge-output-format", "mp4", "-I", items]

        self.current_playlist_downloads = checked_rows
        if not self.run_yt_dlp(args, is_download=True, url=url):
            self.current_playlist_downloads = []
            return

        for row in checked_rows:
            status_item = self.playlist_table.item(row, 1)
            if status_item:
                status_item.setText("Downloading")
                status_item.setForeground(QColor(self.COLORS["info"]))
        self.set_command_controls_enabled(False)

    def check_all_playlist(self):
        """Check all playlist items."""
        for row in range(self.playlist_table.rowCount()):
            checkbox_item = self.playlist_table.item(row, 0)
            if checkbox_item:
                checkbox_item.setCheckState(Qt.CheckState.Checked)

    def uncheck_all_playlist(self):
        """Uncheck all playlist items."""
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
            args = split_cli_args(custom_args)
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

    def run_yt_dlp(
        self, args, output_widget=None, *, is_download=False, format_display="", url=None
    ):
        """Build a command and start a worker with output and progress handlers."""
        if self.warn_if_ytdlp_command_running():
            return False

        target_url = url if url is not None else self.url_input.text().strip()

        output_template = build_output_template(format_display)
        args = self.build_ytdlp_args(args, is_download=is_download, output_template=output_template)
        if args is None:
            return False

        header = (
            f"Running: yt-dlp {' '.join(args)}\n"
            f"URL: {target_url}\n"
            + "-" * 60
            + "\n"
        )
        self.clear_terminal_output()
        self.append_terminal_output(header)

        if output_widget and output_widget is not self.terminal_window:
            output_widget.clear()
            self.append_worker_output(output_widget, header)

        self.statusBar().showMessage("Running yt-dlp...")
        self.set_command_controls_enabled(False)

        if is_download:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.progress_bar.setTextVisible(True)
            self.status_label.setText("Starting download...")
            self.abort_btn.setEnabled(True)
        else:
            self.cancel_advanced_btn.setEnabled(True)

        self.download_thread = DownloadThread(args, target_url, self.get_ytdlp_path())
        self.track_worker_thread(self.download_thread)
        self.download_thread.is_download = is_download
        self.download_thread.output.connect(self.append_terminal_output)
        if output_widget and output_widget is not self.terminal_window:
            self.connect_worker_output(self.download_thread, output_widget)
        if is_download:
            self.download_thread.progress.connect(self.update_progress)
        self.download_thread.finished_signal.connect(self.on_download_thread_finished)
        self.download_thread.start()
        return True

    def cancel_advanced_command(self):
        """Cancel a running non-download command started from the Advanced tab."""
        thread = self.download_thread
        if not thread or not thread.isRunning() or getattr(thread, "is_download", True):
            return
        self.cancel_advanced_btn.setEnabled(False)
        self.statusBar().showMessage("Cancelling command...")
        thread.stop()

    def update_progress(self, percentage, status):
        """Update progress bar and status label."""
        self.progress_bar.setValue(percentage)
        self.status_label.setText(status)

    def abort_download(self):
        """Abort the current download."""
        if not self.download_thread or not self.download_thread.isRunning():
            return

        reply = QMessageBox.question(
            self,
            "Abort Download",
            "Are you sure you want to abort the current download?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            thread = self.download_thread
            if not thread or not thread.isRunning():
                return
            self.status_label.setText("Aborting download...")
            self.abort_btn.setEnabled(False)
            thread.stop()

    def _update_playlist_download_statuses(self, status_text, color_key):
        """Update playlist table status cells for the finished playlist download."""
        for row in self.current_playlist_downloads:
            status_item = self.playlist_table.item(row, 1)
            if status_item:
                status_item.setText(status_text)
                status_item.setForeground(QColor(self.COLORS[color_key]))
        self.current_playlist_downloads = []

    def on_download_finished(self, exit_code, is_download, stop_requested=False):
        """Restore controls and update status after a command finishes."""
        self.download_thread = None
        if self.is_closing:
            return

        was_aborted = stop_requested and exit_code != 0

        self.append_terminal_output("\n" + "-" * 60 + "\n")
        if exit_code == 0:
            self.append_terminal_output("✓ Command completed successfully!\n")
            self.statusBar().showMessage("Command completed successfully!", 5000)
            if is_download:
                self.progress_bar.setValue(100)
                self.status_label.setText("✓ Download completed successfully!")
                self.abort_btn.setEnabled(False)
                self._update_playlist_download_statuses("Completed", "success")
        elif was_aborted:
            self.append_terminal_output("⚠ Command cancelled by user\n")
            self.statusBar().showMessage("Download aborted", 5000)
            if is_download:
                self.status_label.setText("⚠ Download aborted by user")
                self.abort_btn.setEnabled(False)
                self._update_playlist_download_statuses("Aborted", "warning")
        else:
            self.append_terminal_output(f"✗ Command failed with exit code {exit_code}\n")
            self.statusBar().showMessage(f"Command failed with exit code {exit_code}", 5000)
            if is_download:
                self.status_label.setText(f"✗ Download failed with exit code {exit_code}")
                self.abort_btn.setEnabled(False)
                self._update_playlist_download_statuses("Failed", "error")

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

        self._cancel_active_thumbnail_reply()

        download_stopped = self.stop_worker_thread(self.download_thread)
        format_fetcher_stopped = self.stop_worker_thread(self.format_fetcher)
        playlist_fetcher_stopped = self.stop_worker_thread(self.playlist_fetcher)
        extra_threads_stopped = all(
            self.stop_worker_thread(thread) for thread in list(self._worker_threads)
        )

        if (
            not download_stopped
            or not format_fetcher_stopped
            or not playlist_fetcher_stopped
            or not extra_threads_stopped
        ):
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
                self.terminal_window.cleared.disconnect(self.on_terminal_cleared)
            except (RuntimeError, TypeError):
                pass
            self.terminal_window.close()
            self.terminal_window.deleteLater()
            self.terminal_window = None
        self._terminal_buffer.clear()

        return True

    def closeEvent(self, event):
        """Handle application close - cleanup running processes."""
        if not self.cleanup_for_exit(interactive=True):
            event.ignore()
            return

        event.accept()

    def get_config_file_path(self):
        """Return the settings path, using a persistent user directory for packaged apps."""
        if sys.platform == "win32" or getattr(sys, "frozen", False):
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
                with open(config_file, "r", encoding="utf-8") as f:
                    settings = json.load(f)

                if not isinstance(settings, dict):
                    raise ValueError("Settings file must contain a JSON object")

                self.destination_input.setText(str(settings.get("destination") or ""))
                self.ytdlp_path_input.setText(str(settings.get("ytdlp_path") or ""))
                self.ffmpeg_path_input.setText(str(settings.get("ffmpeg_path") or ""))
                self.custom_options_input.setText(str(settings.get("custom_options") or ""))
                self.limit_rate_input.setText(str(settings.get("limit_rate") or ""))
                self.throttled_rate_input.setText(str(settings.get("throttled_rate") or ""))
                self.show_auto_captions_checkbox.setChecked(
                    bool(settings.get("show_auto_captions", False))
                )
                saved_container = str(settings.get("video_container") or "mp4")
                container_idx = self.video_container_combo.findData(saved_container)
                if container_idx >= 0:
                    self.video_container_combo.setCurrentIndex(container_idx)
                saved_audio_fmt = str(settings.get("audio_format") or "original")
                audio_fmt_idx = self.audio_format_combo.findData(saved_audio_fmt)
                if audio_fmt_idx >= 0:
                    self.audio_format_combo.setCurrentIndex(audio_fmt_idx)

                if migrate_legacy_settings:
                    self.config_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(self.config_file, "w", encoding="utf-8") as f:
                        json.dump(settings, f, indent=2)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
            print(f"Error loading settings: {e}")

    def mark_dependency_status_dirty(self, *_args):
        """Mark About dependency statuses stale when tool paths or options change."""
        self._dependency_status_dirty = True

    def refresh_dependency_statuses(self, *, force=False):
        """Re-check yt-dlp, FFmpeg, and JS runtime statuses for the About tab."""
        if not force and not self._dependency_status_dirty:
            return
        self._dependency_status_dirty = False
        self.check_ytdlp_version(show_warning=False, async_mode=True)
        self.check_ffmpeg_version(async_mode=True)
        self.check_js_runtime_version(async_mode=True)

    def on_tab_changed(self, index):
        """Refresh stale dependency statuses when the user opens the About tab."""
        if self.tabs.widget(index) is getattr(self, "about_scroll_area", None):
            self.refresh_dependency_statuses()

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

        self.ytdlp_path_input.textChanged.connect(self.mark_dependency_status_dirty)
        self.ffmpeg_path_input.textChanged.connect(self.mark_dependency_status_dirty)
        self.custom_options_input.textChanged.connect(self.invalidate_js_runtime_cache)
        self.custom_options_input.textChanged.connect(self.mark_dependency_status_dirty)
        self.video_container_combo.currentIndexChanged.connect(self.schedule_settings_save)
        self.audio_format_combo.currentIndexChanged.connect(self.schedule_settings_save)

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
            "video_container": self.video_container_combo.currentData(),
            "audio_format": self.audio_format_combo.currentData(),
        }

    def save_settings(self, show_feedback=True):
        """Persist current preferences and optionally display save feedback."""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.get_settings_data(), f, indent=2)

            if show_feedback:
                self.refresh_dependency_statuses()
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
