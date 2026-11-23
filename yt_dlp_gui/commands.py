"""Build yt-dlp command arguments from GUI settings and format selections."""

import os
import re
import shlex
import sys
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QMessageBox, QWidget

from .formatters import format_filesize


_UNSAFE_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*%#\x00-\x1f]+')


def split_cli_args(raw_args: str, *, posix: bool | None = None) -> list[str]:
    """Split CLI arguments while preserving Windows backslash paths."""
    use_posix = (sys.platform != "win32") if posix is None else posix
    if use_posix:
        return shlex.split(raw_args, posix=True)

    tokens = []
    current: list[str] = []
    quote_char: str | None = None
    in_token = False

    for char in raw_args:
        if quote_char is not None:
            if char == quote_char:
                quote_char = None
            else:
                current.append(char)
        elif char in ('"', "'"):
            quote_char = char
            in_token = True
        elif char.isspace():
            if in_token:
                tokens.append("".join(current))
                current = []
                in_token = False
        else:
            current.append(char)
            in_token = True

    if quote_char is not None:
        raise ValueError("No closing quotation")
    if in_token:
        tokens.append("".join(current))
    return tokens


def sanitize_format_display(format_display: str, max_length: int = 60) -> str:
    """Sanitize a format label so it is safe inside a yt-dlp output filename template."""
    if not format_display:
        return ""
    sanitized = _UNSAFE_FILENAME_CHARS.sub("_", format_display)
    sanitized = re.sub(r"\s+", " ", sanitized).strip(" ._-")
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip(" ._-")
    return sanitized


def build_output_template(format_display: str, *, fallback_format_id: bool = False) -> str | None:
    """Build a safe yt-dlp -o output template from a format display label."""
    safe_display = sanitize_format_display(format_display)
    if safe_display:
        return f"%(title)s [{safe_display}].%(ext)s"
    if fallback_format_id:
        return "%(title)s [%(format_id)s].%(ext)s"
    return None


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
    video_container_combo: Any
    audio_format_combo: Any
    format_data: dict[str, dict[str, Any]]

    if TYPE_CHECKING:
        get_js_runtime_args: Callable[[], list[str]]
        get_ffmpeg_path: Callable[[], str]
        add_subtitle_args: Callable[..., None]

    def get_custom_options_args(self):
        """Parse custom yt-dlp options entered in the UI."""
        custom_options = self.custom_options_input.text().strip()
        if not custom_options:
            return []

        try:
            return split_cli_args(custom_options)
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

        if is_download:
            rate_limit_args = self.get_rate_limit_args()
            if rate_limit_args is None:
                return None
            args.extend(rate_limit_args)

        global_args = self.get_global_ytdlp_args()
        if is_download and "--newline" not in args and "--newline" not in global_args:
            args.append("--newline")

        if global_args:
            args = global_args + args

        if is_download:
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
                short_side = min(int(match.group(1)), int(match.group(2)))
                return f"{short_side}p"
            return "video"

        match = re.search(r"\b(mp3|m4a|webm|opus|aac|ogg|flac|wav)\b", text, re.IGNORECASE)
        if match:
            return match.group(1).lower()
        return "audio"

    def _is_muxed_format(self, format_id: str) -> bool:
        """Return True if format_id is a known combined video+audio format."""
        fmt = self.format_data.get(format_id) if hasattr(self, "format_data") else None
        if not isinstance(fmt, dict):
            return False
        vcodec = fmt.get("vcodec") or "none"
        acodec = fmt.get("acodec") or "none"
        return vcodec != "none" and acodec != "none"

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
            if video_id == "none":
                format_id = audio_id if audio_id else "bestaudio"
                format_display = "audio only"
            elif audio_id == "none":
                format_id = video_id if video_id else "bestvideo"
                format_display = "video only"
            elif (
                video_id
                and self._is_muxed_format(video_id)
                and audio_id in ("", "bestaudio", None)
            ):
                format_id = video_id
                format_display = self.extract_simple_format_display(video_text, is_video=True)
            elif video_id == "bestvideo" and audio_id == "bestaudio":
                format_id = "bv*+ba/b"
                format_display = "best+audio"
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
                format_id = "bv*+ba/b"
                format_display = "best"

        args = ["-f", format_id]

        custom_args = self.get_custom_options_args()
        if "--yes-playlist" not in custom_args and "--no-playlist" not in custom_args:
            args.append("--no-playlist")

        is_audio_only = video_id == "none" and not manual_format
        if is_audio_only:
            audio_format = (
                self.audio_format_combo.currentData()
                if hasattr(self, "audio_format_combo")
                else "original"
            )
            if audio_format and audio_format != "original":
                args.extend(["-x", "--audio-format", audio_format])

        self.add_subtitle_args(args, embed=not is_audio_only)

        if "+" in format_id:
            video_container = (
                self.video_container_combo.currentData()
                if hasattr(self, "video_container_combo")
                else "mp4"
            )
            if video_container and video_container != "original":
                args.extend(["--merge-output-format", video_container])

        return args, format_id, format_display

    def calculate_format_size(self, format_id):
        """Calculate total size for the given format ID."""
        if not hasattr(self, "format_data") or not format_id:
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

        if has_dynamic_part:
            return "Partial" if total_bytes and has_known_part else "Dynamic"

        return format_filesize(total_bytes, compact=False)
