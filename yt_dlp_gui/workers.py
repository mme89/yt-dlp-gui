"""Background Qt workers for yt-dlp metadata fetching and downloads."""

import json
import re
import subprocess

from PySide6.QtCore import QThread, Signal

from .process_utils import hidden_subprocess_kwargs


class FormatFetcher(QThread):
    """Thread for fetching formats without blocking UI."""

    finished = Signal(dict)
    error = Signal(str)
    output = Signal(str)

    def __init__(self, url, ytdlp_path="yt-dlp", args_without_url=None):
        super().__init__()
        self.url = url
        self.ytdlp_path = ytdlp_path
        self.args_without_url = args_without_url or []
        self.process = None

    def run(self):
        try:
            cmd_args = self.args_without_url + [self.url]
            self.output.emit(f"Analyzing video: {self.url}\n")
            self.output.emit(f"Running: {self.ytdlp_path} {' '.join(cmd_args)}\n")
            self.output.emit("-" * 60 + "\n")

            self.process = subprocess.Popen(
                [self.ytdlp_path, *cmd_args],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                **hidden_subprocess_kwargs(),
            )

            self.output.emit("Fetching video information...\n")
            stdout, stderr = self.process.communicate()

            if self.process.returncode != 0:
                error_output = stderr or ""
                self.output.emit(f"\nError output:\n{error_output}\n")
                self.error.emit("Failed to fetch formats")
                return

            output = stdout or ""
            self.output.emit("Successfully retrieved video information!\n")
            self.output.emit("-" * 60 + "\n")

            data = json.loads(output)
            self.finished.emit(data)
        except (OSError, RuntimeError, json.JSONDecodeError) as e:
            self.output.emit(f"\nException: {str(e)}\n")
            self.error.emit(str(e))
        finally:
            self.process = None

    def stop(self, force=False):
        """Stop the running yt-dlp metadata process."""
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                if force:
                    try:
                        self.process.wait(timeout=1.5)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
            except (OSError, subprocess.SubprocessError):
                pass


class DownloadThread(QThread):
    """Thread for downloading without blocking UI."""

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
        self.is_download = True

    @property
    def stop_requested(self):
        """Return whether the UI requested this worker to stop."""
        return self._should_stop

    def run(self):
        try:
            self.process = subprocess.Popen(
                [self.ytdlp_path, *self.args, self.url],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                **hidden_subprocess_kwargs(),
            )

            if self.process.stdout:
                for line in self.process.stdout:
                    if not line:
                        continue
                    self.output.emit(line)
                    self._parse_progress(line)

            exit_code = self.process.wait()
            if self._should_stop and exit_code != 0:
                exit_code = -15
            self.finished_signal.emit(exit_code)
        finally:
            if self.process and self.process.stdout:
                self.process.stdout.close()
            self.process = None

    def _parse_progress(self, text):
        """Parse yt-dlp output for progress information."""
        match = re.search(r"\[download\]\s+(\d+\.?\d*)%", text)
        if match:
            percentage = float(match.group(1))

            status_parts = []

            size_match = re.search(r"of\s+([\d.]+\w+)", text)
            if size_match:
                status_parts.append(f"of {size_match.group(1)}")

            speed_match = re.search(r"at\s+([\d.]+\w+/s)", text)
            if speed_match:
                status_parts.append(f"at {speed_match.group(1)}")

            eta_match = re.search(r"ETA\s+([\d:]+)", text)
            if eta_match:
                status_parts.append(f"ETA {eta_match.group(1)}")

            status = " ".join(status_parts) if status_parts else "Downloading..."
            self.progress.emit(int(percentage), status)

        elif "[download] Destination:" in text:
            filename = text.split("Destination:")[-1].strip()
            self.progress.emit(0, f"Starting download: {filename}")
        elif "[download] 100%" in text or "has already been downloaded" in text:
            self.progress.emit(100, "Download complete!")
        elif "[Merger]" in text or "Merging formats" in text:
            self.progress.emit(100, "Merging video and audio...")
        elif "[ExtractAudio]" in text:
            self.progress.emit(100, "Extracting audio...")
        elif "[EmbedSubtitle]" in text:
            self.progress.emit(100, "Embedding subtitles...")

    def stop(self):
        """Request the download to stop."""
        self._should_stop = True
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except (OSError, subprocess.SubprocessError):
                pass

    def stop_and_wait(self, timeout_ms=3000):
        """Stop the download process and wait briefly before killing it."""
        self._should_stop = True
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                try:
                    self.process.wait(timeout=timeout_ms / 1000)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            except (OSError, subprocess.SubprocessError):
                pass
