"""Executable discovery, JS runtime detection, and dependency version probing."""

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from PySide6.QtWidgets import QMessageBox, QWidget

from .compatibility import RECOMMENDED_YTDLP_VERSION, is_supported_runtime, needs_ytdlp_update
from .process_utils import hidden_subprocess_kwargs
from .workers import ProbeWorker


class ProbeMixin:
    """Mixin providing executable lookup and async/sync dependency version probes."""

    COLORS: dict[str, str]
    ytdlp_path_input: Any
    ffmpeg_path_input: Any
    ytdlp_version_label: Any
    ffmpeg_version_label: Any
    js_runtime_version_label: Any
    ytdlp_ejs_status_label: Any
    ytdlp_version: Any
    ffmpeg_version: Any
    js_runtime_version: Any
    js_runtime_info: Any
    js_runtime_cache_dirty: bool
    ytdlp_ejs_status: Any
    is_closing: bool
    _probe_workers: dict[str, Any]

    if TYPE_CHECKING:
        get_custom_options_args: Callable[[], list[str]]
        track_worker_thread: Callable[[Any], None]
        statusBar: Callable[[], Any]

    def find_executable(self, name):
        """Find executable in PATH first, then common platform locations."""
        which_path = shutil.which(name)
        if which_path:
            return which_path

        has_separator = os.path.sep in name or (
            os.path.altsep is not None and os.path.altsep in name
        )
        if has_separator and os.path.isfile(name) and os.access(name, os.X_OK):
            return name

        if sys.platform == "darwin":
            common_paths = [
                f"/usr/local/bin/{name}",
                f"/opt/homebrew/bin/{name}",
                f"/opt/local/bin/{name}",
                f"/usr/bin/{name}",
                os.path.expanduser(f"~/.local/bin/{name}"),
            ]
        elif sys.platform == "win32":
            exe_name = name if name.endswith(".exe") else f"{name}.exe"
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

        return name

    def get_ytdlp_path(self):
        """Get the yt-dlp path from settings."""
        ytdlp_path = self.ytdlp_path_input.text().strip()
        if ytdlp_path:
            return os.path.expanduser(ytdlp_path)
        return self.find_executable("yt-dlp")

    def get_ffmpeg_path(self):
        """Get the ffmpeg path from settings."""
        ffmpeg_path = self.ffmpeg_path_input.text().strip()
        if ffmpeg_path:
            return os.path.expanduser(ffmpeg_path)
        return self.find_executable("ffmpeg")

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

    def _detect_js_runtime(self, custom_args=None):
        """Detect the JS runtime yt-dlp will use."""
        if custom_args is None:
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
            runtime_name = runtime_name.strip().lower()
            runtime_path = os.path.expanduser(runtime_path.strip()) if runtime_path.strip() else ""

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
                "Deno": "deno",
                "Node": "node",
                "QuickJS": "qjs",
                "Bun": "bun",
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

    def _start_probe_worker(self, key, probe_fn, on_result):
        """Run a dependency probe in the background and deliver only the latest result."""
        previous = self._probe_workers.get(key)
        if previous is not None:
            previous.stop()
        worker = ProbeWorker(probe_fn)
        self._probe_workers[key] = worker
        self.track_worker_thread(worker)

        def handle_result(result, current=worker):
            if self.is_closing or self._probe_workers.get(key) is not current:
                return
            self._probe_workers[key] = None
            on_result(result)

        worker.result_ready.connect(handle_result)
        worker.start()

    def _probe_js_runtime(self, custom_args):
        """Run JS runtime detection and version lookup without touching Qt widgets."""
        runtime_info = self._detect_js_runtime(custom_args=custom_args)
        version_line = None
        if runtime_info:
            version_line = runtime_info.get("version")
            if version_line is None and runtime_info["path"]:
                version_line = self.get_runtime_version(runtime_info["name"], runtime_info["path"])
        return runtime_info, version_line

    def _apply_js_runtime_result(self, result):
        """Update cached JS runtime state and About label from a probe result."""
        runtime_info, version_line = result
        self.js_runtime_info = runtime_info
        self.js_runtime_cache_dirty = False

        if not runtime_info:
            self.js_runtime_version = "Not found"
            self.js_runtime_version_label.setText(
                "⚠️ No supported JS runtime found (Deno 2.3+ or Node.js 22+ recommended)"
            )
            self.js_runtime_version_label.setStyleSheet(
                f"color: {self.COLORS['warning']}; font-style: italic;"
            )
            return

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
            color = self.COLORS["warning" if runtime_info["name"] == "Bun" else "success"]
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

    def check_js_runtime_version(self, *, async_mode=False):
        """Check which JS runtime yt-dlp will use and display its status."""
        if async_mode:
            custom_args = self.get_custom_options_args()
            self._start_probe_worker(
                "js_runtime",
                lambda: self._probe_js_runtime(custom_args),
                self._apply_js_runtime_result,
            )
            return

        runtime_info = self.detect_js_runtime(force_refresh=True)
        version_line = None
        if runtime_info:
            version_line = runtime_info.get("version")
            if version_line is None and runtime_info["path"]:
                version_line = self.get_runtime_version(runtime_info["name"], runtime_info["path"])
        ProbeMixin._apply_js_runtime_result(self, (runtime_info, version_line))

    def check_ytdlp_ejs_status(self):
        """The GUI's Python packages do not describe the external yt-dlp install."""
        self.ytdlp_ejs_status = "Not verified"
        self.ytdlp_ejs_status_label.setText("Managed by your yt-dlp installation (not verified)")
        self.ytdlp_ejs_status_label.setStyleSheet(
            f"color: {self.COLORS['info']}; font-weight: bold;"
        )

    @staticmethod
    def _probe_ytdlp_version(ytdlp_path):
        """Probe yt-dlp --version without touching Qt widgets."""
        try:
            result = subprocess.run(
                [ytdlp_path, "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=3,
                **hidden_subprocess_kwargs(),
            )
            version = (result.stdout or "").strip()
            if result.returncode == 0 and version:
                return "ok", version
            return "not_found", ""
        except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as e:
            return "error", str(e)

    def _apply_ytdlp_version_result(self, result, *, show_warning=True):
        """Update yt-dlp status widgets from a probe result."""
        status, value = result
        if status == "ok":
            self.ytdlp_version = value
            update_recommended = needs_ytdlp_update(value)
            self.ytdlp_version_label.setText(
                f"Installed version: {value}"
                + (
                    f" — update to {RECOMMENDED_YTDLP_VERSION}+ recommended"
                    if update_recommended
                    else ""
                )
            )
            color = self.COLORS["warning" if update_recommended else "success"]
            self.ytdlp_version_label.setStyleSheet(f"color: {color}; font-weight: bold;")
            self.statusBar().showMessage(f"yt-dlp {value} detected", 3000)
        elif status == "not_found":
            self.ytdlp_version = "Not found"
            self.ytdlp_version_label.setText("⚠️ yt-dlp not found - Please install it")
            self.ytdlp_version_label.setStyleSheet(
                f"color: {self.COLORS['error']}; font-weight: bold;"
            )

            if sys.platform == "darwin":
                install_msg = (
                    "yt-dlp is not installed or not in your PATH.\n\n"
                    "Please install it:\n"
                    "• Using Homebrew: brew install yt-dlp\n"
                    "• Or visit: https://github.com/yt-dlp/yt-dlp"
                )
            elif sys.platform == "win32":
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

            if show_warning:
                QMessageBox.warning(cast(QWidget, self), "yt-dlp Not Found", install_msg)
        else:
            self.ytdlp_version = "Error checking version"
            self.ytdlp_version_label.setText("Error checking yt-dlp version")
            self.ytdlp_version_label.setStyleSheet(f"color: {self.COLORS['warning']};")
            print(f"Error checking yt-dlp version: {value}")

    def check_ytdlp_version(self, show_warning=True, *, async_mode=False):
        """Check if yt-dlp is installed and get version."""
        ytdlp_path = self.get_ytdlp_path()
        if async_mode:
            self._start_probe_worker(
                "ytdlp",
                lambda: self._probe_ytdlp_version(ytdlp_path),
                lambda res: self._apply_ytdlp_version_result(res, show_warning=show_warning),
            )
            return

        self._apply_ytdlp_version_result(
            self._probe_ytdlp_version(ytdlp_path),
            show_warning=show_warning,
        )

    @staticmethod
    def _probe_ffmpeg_version(ffmpeg_path):
        """Probe ffmpeg -version without touching Qt widgets."""
        try:
            result = subprocess.run(
                [ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=3,
                **hidden_subprocess_kwargs(),
            )
            output = result.stdout or ""
            if result.returncode == 0 and output.strip():
                first_line = output.split("\n", maxsplit=1)[0]
                if "version" in first_line:
                    return "ok", first_line.split("version")[1].strip().split()[0]
                return "unknown", ""
            return "not_found", ""
        except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as e:
            return "error", str(e)

    def _apply_ffmpeg_version_result(self, result):
        """Update FFmpeg status widgets from a probe result."""
        status, value = result
        if status == "ok":
            self.ffmpeg_version = value
            self.ffmpeg_version_label.setText(f"Installed version: {value}")
            self.ffmpeg_version_label.setStyleSheet(
                f"color: {self.COLORS['success']}; font-weight: bold;"
            )
        elif status == "unknown":
            self.ffmpeg_version = "Unknown"
            self.ffmpeg_version_label.setText("Installed (version unknown)")
            self.ffmpeg_version_label.setStyleSheet(f"color: {self.COLORS['success']};")
        elif status == "not_found":
            self.ffmpeg_version = "Not found"
            self.ffmpeg_version_label.setText("⚠️ FFmpeg not found (optional)")
            self.ffmpeg_version_label.setStyleSheet(
                f"color: {self.COLORS['warning']}; font-style: italic;"
            )
        else:
            self.ffmpeg_version = "Error checking version"
            self.ffmpeg_version_label.setText("FFmpeg status unknown")
            self.ffmpeg_version_label.setStyleSheet(
                f"color: {self.COLORS['text_secondary']}; font-style: italic;"
            )
            print(f"Error checking FFmpeg version: {value}")

    def check_ffmpeg_version(self, *, async_mode=False):
        """Check if FFmpeg is installed and get version."""
        ffmpeg_path = self.get_ffmpeg_path()
        if async_mode:
            self._start_probe_worker(
                "ffmpeg",
                lambda: self._probe_ffmpeg_version(ffmpeg_path),
                self._apply_ffmpeg_version_result,
            )
            return

        self._apply_ffmpeg_version_result(self._probe_ffmpeg_version(ffmpeg_path))
