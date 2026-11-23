"""Background Qt workers for yt-dlp metadata fetching and downloads."""

import json
import re
import subprocess
import threading

from PySide6.QtCore import QThread, Signal

from .process_utils import managed_subprocess_kwargs, terminate_process_tree


class ProbeWorker(QThread):
    """Lightweight background thread for running a single dependency probe callable."""

    result_ready = Signal(object)

    def __init__(self, probe_fn):
        super().__init__()
        self._probe_fn = probe_fn
        self._should_stop = False

    def run(self):
        if self._should_stop:
            return
        result = self._probe_fn()
        if not self._should_stop:
            self.result_ready.emit(result)

    def stop(self, _force=False):
        """Mark the probe cancelled so its result is discarded on completion."""
        self._should_stop = True


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
        self._should_stop = False
        self._process_lock = threading.Lock()

    @property
    def stop_requested(self):
        """Return whether the UI requested this fetcher to stop."""
        return self._should_stop

    def run(self):
        process = None
        try:
            cmd_args = self.args_without_url + [self.url]
            self.output.emit(f"Analyzing video: {self.url}\n")
            self.output.emit(f"Running: {self.ytdlp_path} {' '.join(cmd_args)}\n")
            self.output.emit("-" * 60 + "\n")

            with self._process_lock:
                if self._should_stop:
                    self.error.emit("Cancelled")
                    return
                process = subprocess.Popen(
                    [self.ytdlp_path, *cmd_args],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    **managed_subprocess_kwargs(),
                )
                self.process = process

            self.output.emit("Fetching video information...\n")
            stdout, stderr = process.communicate()

            if process.returncode != 0:
                error_output = stderr or ""
                self.output.emit(f"\nError output:\n{error_output}\n")
                self.error.emit(self._extract_error_message(error_output))
                return

            output = stdout or ""
            self.output.emit("Successfully retrieved video information!\n")
            self.output.emit("-" * 60 + "\n")

            data = json.loads(output)
            self.finished.emit(data)
        except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as e:
            self.output.emit(f"\nException: {str(e)}\n")
            self.error.emit(str(e))
        finally:
            with self._process_lock:
                self.process = None

    @staticmethod
    def _extract_error_message(stderr_text):
        """Extract the most informative error line from yt-dlp stderr."""
        lines = [line.strip() for line in stderr_text.splitlines() if line.strip()]
        for line in reversed(lines):
            if line.startswith("ERROR:"):
                return line.removeprefix("ERROR:").strip() or line
        return lines[-1] if lines else "Failed to fetch formats"

    def stop(self, force=False):
        """Stop the running yt-dlp metadata process and its child tree."""
        with self._process_lock:
            self._should_stop = True
            process = self.process

        terminate_process_tree(process, force=force, timeout=1.5)


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
        self._process_lock = threading.Lock()
        self.is_download = True

    @property
    def stop_requested(self):
        """Return whether the UI requested this worker to stop."""
        return self._should_stop

    def run(self):
        process = None
        try:
            with self._process_lock:
                if self._should_stop:
                    self.finished_signal.emit(-15)
                    return
                process = subprocess.Popen(
                    [self.ytdlp_path, *self.args, self.url],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    **managed_subprocess_kwargs(),
                )
                self.process = process

            if process.stdout:
                for line in process.stdout:
                    if not line:
                        continue
                    self.output.emit(line)
                    self._parse_progress(line)

            exit_code = process.wait()
            if self._should_stop and exit_code != 0:
                exit_code = -15
            self.finished_signal.emit(exit_code)
        except (OSError, subprocess.SubprocessError, ValueError) as e:
            self.output.emit(f"\nFailed to run yt-dlp: {e}\n")
            self.finished_signal.emit(-1)
        finally:
            if process and process.stdout:
                process.stdout.close()
            with self._process_lock:
                self.process = None

    def _parse_progress(self, text):
        """Parse yt-dlp output for progress information."""
        match = re.search(r"\[download\]\s+(\d+\.?\d*)%", text)
        if match:
            percentage = min(100, max(0, int(float(match.group(1)))))

            status_parts = []

            size_match = re.search(r"of\s+(~?\s*[\d.]+\w+)", text)
            if size_match:
                size_str = re.sub(r"\s+", "", size_match.group(1))
                status_parts.append(f"of {size_str}")

            speed_match = re.search(r"at\s+([\d.]+\w+/s|Unknown\s+\S+)", text)
            if speed_match:
                status_parts.append(f"at {speed_match.group(1)}")

            eta_match = re.search(r"ETA\s+([\d:]+|Unknown)", text)
            if eta_match:
                status_parts.append(f"ETA {eta_match.group(1)}")

            status = " ".join(status_parts) if status_parts else "Downloading..."
            self.progress.emit(percentage, status)

        elif "[download] Destination:" in text:
            filename = text.split("Destination:")[-1].strip()
            self.progress.emit(0, f"Starting download: {filename}")
        elif "has already been downloaded" in text:
            self.progress.emit(100, "Download complete!")
        elif "[Merger]" in text or "Merging formats" in text:
            self.progress.emit(100, "Merging video and audio...")
        elif "[ExtractAudio]" in text:
            self.progress.emit(100, "Extracting audio...")
        elif "[EmbedSubtitle]" in text:
            self.progress.emit(100, "Embedding subtitles...")

    def stop(self):
        """Request the download process and its child tree to stop."""
        with self._process_lock:
            self._should_stop = True
            process = self.process

        terminate_process_tree(process, force=False)

    def stop_and_wait(self, timeout_ms=3000):
        """Stop the download process tree and wait briefly before killing it."""
        with self._process_lock:
            self._should_stop = True
            process = self.process

        terminate_process_tree(process, force=True, timeout=timeout_ms / 1000)
