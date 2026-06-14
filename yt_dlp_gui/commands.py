# pylint: disable=no-name-in-module
import os
import re
import shlex
from typing import Any, cast

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QMessageBox, QWidget


class CommandMixin:
    """Helpers for building yt-dlp command arguments from UI state."""

    RATE_LIMIT_PATTERN = re.compile(r"^\d+(?:\.\d+)?[KMG]?$", re.IGNORECASE)

    custom_options_input: Any
    destination_input: Any
    limit_rate_input: Any
    throttled_rate_input: Any
    format_input: Any
    video_combo: Any
    audio_combo: Any
    format_data: dict[str, dict[str, Any]]

    def get_js_runtime_args(self) -> list[str]:
        """Return JS runtime args supplied by the main window."""
        raise NotImplementedError

    def get_ffmpeg_path(self) -> str:
        """Return the configured ffmpeg path supplied by the main window."""
        raise NotImplementedError

    def add_subtitle_args(self, args: list[str]) -> None:
        """Append subtitle args supplied by the main window."""
        raise NotImplementedError

    def get_custom_options_args(self):
        """Parse custom yt-dlp options entered in the UI."""
        custom_options = self.custom_options_input.text().strip()
        if not custom_options:
            return []

        try:
            return shlex.split(custom_options)
        except ValueError:
            return custom_options.split()

    def get_global_ytdlp_args(self):
        """Return yt-dlp options that should apply to every operation."""
        return self.get_custom_options_args() + self.get_js_runtime_args()

    def get_destination_path(self):
        """Return the configured destination, or the OS Downloads folder."""
        destination = self.destination_input.text().strip()
        if destination:
            return os.path.expanduser(destination)

        downloads_path = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DownloadLocation
        )
        return downloads_path or os.path.expanduser("~/Downloads")

    def get_rate_limit_args(self):
        """Return validated rate-limit arguments, or None when invalid."""
        args = []
        rate_fields = (
            ("Maximum download rate", "--limit-rate", self.limit_rate_input),
            ("Minimum download rate", "--throttled-rate", self.throttled_rate_input),
        )

        for label, option, input_widget in rate_fields:
            value = input_widget.text().strip()
            if not value:
                continue

            if not self.RATE_LIMIT_PATTERN.fullmatch(value):
                QMessageBox.warning(
                    cast(QWidget, self),
                    "Invalid Rate Limit",
                    f"{label} must be a number optionally followed by K, M, or G "
                    "(examples: 50K, 4.2M, 1G).",
                )
                return None

            args.extend([option, value])

        return args

    def build_ytdlp_args(self, operation_args, is_download=False, output_template=None):
        """Build final yt-dlp arguments with common app settings applied consistently."""
        args = list(operation_args)

        if output_template:
            args.extend(["-o", output_template])

        rate_limit_args = self.get_rate_limit_args()
        if rate_limit_args is None:
            return None
        args.extend(rate_limit_args)

        global_args = self.get_global_ytdlp_args()
        if is_download and "--newline" not in args and "--newline" not in global_args:
            args.append("--newline")

        if global_args:
            args = global_args + args

        args = ["-P", self.get_destination_path()] + args

        ffmpeg_path = self.get_ffmpeg_path()
        if ffmpeg_path and ffmpeg_path != "ffmpeg":
            args = ["--ffmpeg-location", ffmpeg_path] + args

        return args

    def extract_simple_format_display(self, text, is_video=True):
        """Return a compact display label for a selected format row."""
        if is_video:
            match = re.search(r"(\d+)x(\d+)", text)
            if match:
                return f"{match.group(2)}p"
            return "video"

        match = re.search(r"\b(mp3|m4a|webm|opus|aac|ogg|flac|wav)\b", text, re.IGNORECASE)
        if match:
            return match.group(1).lower()
        return "audio"

    def build_selected_download_args(self):
        """Return download args, format id, and display label for the current selection."""
        manual_format = self.format_input.text().strip()
        video_id = None
        audio_id = None

        if manual_format:
            format_id = manual_format
            format_display = manual_format
        else:
            video_id = self.video_combo.currentData()
            audio_id = self.audio_combo.currentData()
            video_text = self.video_combo.currentText()
            audio_text = self.audio_combo.currentText()

            if video_id == "none" and audio_id == "none":
                QMessageBox.warning(
                    cast(QWidget, self),
                    "Error",
                    "Cannot download with both video and audio set to 'none'!",
                )
                return None
            elif video_id == "none":
                format_id = audio_id if audio_id else "bestaudio"
                format_display = "audio only"
            elif audio_id == "none":
                format_id = video_id if video_id else "bestvideo"
                format_display = "video only"
            elif video_id and audio_id:
                format_id = f"{video_id}+{audio_id}"
                video_part = (
                    "best"
                    if video_id == "bestvideo"
                    else self.extract_simple_format_display(video_text, is_video=True)
                )
                audio_part = (
                    "audio"
                    if audio_id == "bestaudio"
                    else self.extract_simple_format_display(audio_text, is_video=False)
                )
                format_display = f"{video_part}+{audio_part}"
            elif video_id:
                format_id = video_id
                format_display = (
                    "best"
                    if video_id == "bestvideo"
                    else self.extract_simple_format_display(video_text, is_video=True)
                )
            elif audio_id:
                format_id = audio_id
                format_display = (
                    "audio"
                    if audio_id == "bestaudio"
                    else self.extract_simple_format_display(audio_text, is_video=False)
                )
            else:
                format_id = "best"
                format_display = "best"

        args = ["-f", format_id]

        if video_id == "none" and not manual_format:
            args.extend(["-x", "--audio-format", "mp3"])

        self.add_subtitle_args(args)

        if "+" in format_id:
            args.extend(["--merge-output-format", "mp4"])

        return args, format_id, format_display

    def calculate_format_size(self, format_id):
        """Calculate total size for the given format ID."""
        if not hasattr(self, "format_data"):
            return "Unknown"

        if not format_id:
            return "Unknown"

        total_bytes = 0
        has_known_part = False
        has_dynamic_part = False

        for part in format_id.split("+"):
            part = part.strip()
            if not part:
                continue

            if part not in self.format_data:
                has_dynamic_part = True
                continue

            format_info = self.format_data[part]
            has_known_part = True
            filesize = format_info.get("filesize", 0) or format_info.get("filesize_approx", 0)
            if filesize:
                total_bytes += filesize

        if has_dynamic_part and not has_known_part:
            return "Dynamic"

        if has_dynamic_part:
            return "Partial" if total_bytes else "Dynamic"

        if total_bytes == 0:
            return "Unknown"
        elif total_bytes > 1024 * 1024 * 1024:
            return f"{total_bytes / (1024**3):.1f} GB"
        elif total_bytes > 1024 * 1024:
            return f"{total_bytes / (1024**2):.0f} MB"
        else:
            return f"{total_bytes / 1024:.0f} KB"
