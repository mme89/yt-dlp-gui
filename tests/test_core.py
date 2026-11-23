"""Regression tests for workers, command parsing, format handling, and abort safety."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QMessageBox

from yt_dlp_gui.app import YtDlpGUI
from yt_dlp_gui.commands import build_output_template, sanitize_format_display, split_cli_args
from yt_dlp_gui.compatibility import is_supported_runtime, needs_ytdlp_update
from yt_dlp_gui.process_utils import managed_subprocess_kwargs, terminate_process_tree
from yt_dlp_gui.terminal_window import TerminalWindow
from yt_dlp_gui.workers import DownloadThread, FormatFetcher


def qt_application():
    """Create one headless Qt application for worker and window tests."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


class FakeWorker(QObject):
    """Minimal QObject mimicking a QThread's finished signal and deleteLater."""

    finished = Signal()

    def __init__(self):
        super().__init__()
        self.deleted = False

    def deleteLater(self):  # pylint: disable=invalid-name
        """Record deferred deletion."""
        self.deleted = True
        super().deleteLater()


class CommandHelperTests(unittest.TestCase):
    """Verify Windows-safe CLI splitting and filename template sanitization."""

    def test_split_cli_args_preserves_windows_backslashes(self):
        args = split_cli_args(
            r'--cookies C:\Users\alice\cookies.txt --paths "C:\My Videos\yt"',
            posix=False,
        )
        self.assertEqual(
            args,
            ["--cookies", r"C:\Users\alice\cookies.txt", "--paths", r"C:\My Videos\yt"],
        )

    def test_split_cli_args_unquotes_equals_option_on_windows(self):
        args = split_cli_args(
            r'--cookies="C:\My Folder\cookies.txt" --js-runtimes=node:C:\node\node.exe',
            posix=False,
        )
        self.assertEqual(
            args,
            [r"--cookies=C:\My Folder\cookies.txt", r"--js-runtimes=node:C:\node\node.exe"],
        )

    def test_split_cli_args_posix_mode(self):
        args = split_cli_args('--cookies "/tmp/my cookies.txt" --no-mtime', posix=True)
        self.assertEqual(args, ["--cookies", "/tmp/my cookies.txt", "--no-mtime"])

    def test_sanitize_format_display_strips_unsafe_path_and_template_chars(self):
        self.assertEqual(
            sanitize_format_display("bv*[height<=1080]+ba/b"),
            "bv_[height_=1080]+ba_b",
        )
        self.assertEqual(sanitize_format_display("///:::%%%"), "")
        template = build_output_template("bestvideo+bestaudio/best")
        assert template is not None
        self.assertNotIn("/", template)
        self.assertEqual(
            build_output_template("///", fallback_format_id=True),
            "%(title)s [%(format_id)s].%(ext)s",
        )
        self.assertIsNone(build_output_template("///", fallback_format_id=False))


class WorkerTests(unittest.TestCase):
    """Verify worker error handling and stop race safety."""

    @classmethod
    def setUpClass(cls):
        cls.app = qt_application()

    def test_download_thread_emits_failure_when_popen_raises(self):
        worker = DownloadThread(["-f", "bv*+ba/b"], "https://www.youtube.com/watch?v=test")
        exit_codes = []
        outputs = []
        worker.finished_signal.connect(exit_codes.append)
        worker.output.connect(outputs.append)

        with patch("yt_dlp_gui.workers.subprocess.Popen", side_effect=FileNotFoundError("missing")):
            worker.run()

        self.assertEqual(exit_codes, [-1])
        self.assertTrue(any("missing" in line for line in outputs))

    def test_download_thread_honors_stop_before_popen(self):
        worker = DownloadThread(["-f", "bv*+ba/b"], "https://www.youtube.com/watch?v=test")
        exit_codes = []
        worker.finished_signal.connect(exit_codes.append)
        worker.stop()

        with patch("yt_dlp_gui.workers.subprocess.Popen") as popen:
            worker.run()
            popen.assert_not_called()

        self.assertEqual(exit_codes, [-15])

    def test_format_fetcher_honors_stop_before_popen(self):
        fetcher = FormatFetcher("https://www.youtube.com/watch?v=test")
        errors = []
        fetcher.error.connect(errors.append)
        fetcher.stop()

        with patch("yt_dlp_gui.workers.subprocess.Popen") as popen:
            fetcher.run()
            popen.assert_not_called()

        self.assertEqual(errors, ["Cancelled"])


class MainWindowFixTests(unittest.TestCase):
    """Verify format parsing, muxed YouTube formats, abort race, and thread tracking."""

    @classmethod
    def setUpClass(cls):
        cls.app = qt_application()

    def setUp(self):
        self.patches = [
            patch.object(YtDlpGUI, name)
            for name in (
                "load_settings",
                "setup_settings_autosave",
                "save_settings",
                "check_ytdlp_version",
                "check_ffmpeg_version",
                "check_js_runtime_version",
                "check_ytdlp_ejs_status",
            )
        ]
        for item in self.patches:
            item.start()
        self.window = YtDlpGUI()
        self.window.update_startup_timer.stop()
        self.window.update_timer.stop()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        for item in self.patches:
            item.stop()

    def test_on_formats_fetched_handles_none_metadata_and_muxed_formats(self):
        fake_fetcher = Mock()
        self.window.format_fetcher = fake_fetcher
        payload = {
            "title": "Test YouTube Video",
            "formats": [
                {
                    "format_id": "137",
                    "ext": "mp4",
                    "vcodec": "avc1",
                    "acodec": "none",
                    "resolution": "1920x1080",
                    "height": 1080,
                    "fps": 30,
                    "filesize": 50_000_000,
                },
                {
                    "format_id": "sb0",
                    "ext": "mhtml",
                    "vcodec": "images",
                    "acodec": "none",
                    "resolution": "storyboard",
                    "height": None,
                    "fps": None,
                },
                {
                    "format_id": "18",
                    "ext": "mp4",
                    "vcodec": "avc1",
                    "acodec": "mp4a",
                    "resolution": "640x360",
                    "height": 360,
                    "fps": 30,
                    "filesize_approx": 12_000_000,
                },
                {
                    "format_id": "140",
                    "ext": "m4a",
                    "vcodec": "none",
                    "acodec": "mp4a",
                    "abr": None,
                },
                {
                    "format_id": "251",
                    "ext": "webm",
                    "vcodec": "none",
                    "acodec": "opus",
                    "abr": 160,
                },
            ],
            "subtitles": None,
            "automatic_captions": None,
        }

        with patch.object(self.window, "sender", return_value=fake_fetcher):
            self.window.on_formats_fetched(payload)

        video_items = [
            (self.window.video_combo.itemText(i), self.window.video_combo.itemData(i))
            for i in range(self.window.video_combo.count())
        ]
        self.assertTrue(any(fid == "18" and "[video+audio]" in text for text, fid in video_items))
        self.assertTrue(self.window.analyze_btn.isEnabled())

        # Default best+best falls back to muxed when needed via bv*+ba/b.
        selection = self.window.build_selected_download_args()
        assert selection is not None
        args, fmt_id, _ = selection
        self.assertEqual(fmt_id, "bv*+ba/b")
        self.assertIn("bv*+ba/b", args)

        # Selecting muxed format 18 with default Best audio does not append +bestaudio.
        idx_18 = self.window.video_combo.findData("18")
        self.window.video_combo.setCurrentIndex(idx_18)
        selection = self.window.build_selected_download_args()
        assert selection is not None
        args, fmt_id, display = selection
        self.assertEqual(fmt_id, "18")
        self.assertEqual(args, ["-f", "18", "--no-playlist"])
        self.assertEqual(display, "360p")

        # Explicitly picking an audio stream still combines 18+251.
        idx_251 = self.window.audio_combo.findData("251")
        self.window.audio_combo.setCurrentIndex(idx_251)
        selection = self.window.build_selected_download_args()
        assert selection is not None
        args, fmt_id, _ = selection
        self.assertEqual(fmt_id, "18+251")
        self.assertIn("--merge-output-format", args)
        self.assertIn("--no-playlist", args)

    def test_version_checks_do_not_report_timeout_as_installed(self):
        for item in self.patches:
            if item.attribute in ("check_ytdlp_version", "check_ffmpeg_version"):
                item.stop()
        with patch(
            "yt_dlp_gui.probes.subprocess.run",
            side_effect=subprocess.TimeoutExpired("yt-dlp", 3),
        ):
            self.window.check_ytdlp_version()
            self.window.check_ffmpeg_version()

        self.assertEqual(self.window.ytdlp_version, "Error checking version")
        self.assertEqual(self.window.ffmpeg_version, "Error checking version")

    def test_build_ytdlp_args_skips_download_only_flags_for_metadata(self):
        self.window.limit_rate_input.setText("not-a-rate")
        args = self.window.build_ytdlp_args(["--no-playlist", "-J"], is_download=False)
        self.assertIsNotNone(args)
        assert args is not None
        self.assertNotIn("-P", args)
        self.assertNotIn("--limit-rate", args)

        with patch("yt_dlp_gui.commands.QMessageBox.warning") as warn:
            download_args = self.window.build_ytdlp_args(["-f", "18"], is_download=True)
            self.assertIsNone(download_args)
            warn.assert_called_once()

    def test_find_executable_prefers_path(self):
        with patch("yt_dlp_gui.probes.shutil.which", return_value="/custom/venv/bin/yt-dlp"):
            self.assertEqual(self.window.find_executable("yt-dlp"), "/custom/venv/bin/yt-dlp")

    def test_subtitle_edge_cases(self):
        self.window.automatic_captions = {"en": [{"ext": "vtt"}]}
        self.window.show_auto_captions_checkbox.setChecked(True)
        self.window.subtitle_combo.clear()
        self.window.subtitle_combo.addItem("All subtitles", "all")
        self.window.subtitle_combo.addItem("en (auto)", "en")

        # "All subtitles" should not flood with --write-auto-subs.
        self.window.subtitle_combo.setCurrentIndex(0)
        args = []
        self.window.add_subtitle_args(args, embed=True)
        self.assertNotIn("--write-auto-subs", args)
        self.assertIn("--embed-subs", args)

        # Specific auto-caption without "Keep subtitle files" adds --compat-options no-keep-subs.
        self.window.subtitle_combo.setCurrentIndex(1)
        self.window.keep_subtitle_files_checkbox.setChecked(False)
        args = []
        self.window.add_subtitle_args(args, embed=True)
        self.assertIn("--write-auto-subs", args)
        self.assertIn("--compat-options", args)
        self.assertIn("no-keep-subs", args)

        # Audio-only download does not pass --embed-subs.
        self.window.video_combo.clear()
        self.window.video_combo.addItem("No video (audio only)", "none")
        self.window.audio_combo.clear()
        self.window.audio_combo.addItem("Best audio", "bestaudio")
        self.window.audio_format_combo.setCurrentIndex(
            self.window.audio_format_combo.findData("mp3")
        )
        selection = self.window.build_selected_download_args()
        assert selection is not None
        dl_args, _, _ = selection
        self.assertIn("-x", dl_args)
        self.assertNotIn("--embed-subs", dl_args)
        self.assertIn("--write-auto-subs", dl_args)

    def test_stale_thumbnail_reply_is_ignored(self):
        stale_reply = Mock()
        active_reply = Mock()
        self.window.active_thumbnail_reply = active_reply
        with patch.object(self.window, "sender", return_value=stale_reply):
            self.window.on_thumbnail_loaded()

        self.assertIs(self.window.active_thumbnail_reply, active_reply)
        stale_reply.deleteLater.assert_called_once()
        active_reply.deleteLater.assert_not_called()

    def test_queue_state_guards_and_stale_title(self):
        self.window.is_processing_queue = True
        self.window.download_queue = [
            {
                "url": "https://www.youtube.com/watch?v=1",
                "args": ["-f", "18"],
                "format": "18",
                "format_display": "360p",
                "title": "One",
                "size": "10 MB",
                "status": "Downloading",
            }
        ]
        self.window.set_command_controls_enabled(False)
        self.assertTrue(self.window.add_to_queue_btn.isEnabled())
        self.assertFalse(self.window.clear_queue_btn.isEnabled())

        with patch("yt_dlp_gui.app.QMessageBox.warning") as warn:
            self.window.clear_queue()
            warn.assert_called_once()
        self.assertEqual(len(self.window.download_queue), 1)

        # Adding a different URL than analyzed_url does not copy stale title.
        self.window.analyzed_url = "https://www.youtube.com/watch?v=old"
        self.window.title_label.setText("Title: Old Video")
        self.window.url_input.setText("https://www.youtube.com/watch?v=new")
        with patch("yt_dlp_gui.app.QMessageBox.information"):
            self.window.add_to_queue()
        self.assertEqual(self.window.download_queue[-1]["title"], "Unknown")

    def test_playlist_download_uses_loaded_url_and_handles_start_failure(self):
        fake_fetcher = Mock(url="https://www.youtube.com/playlist?list=PL123")
        self.window.playlist_fetcher = fake_fetcher
        with patch.object(self.window, "sender", return_value=fake_fetcher):
            self.window.on_playlist_loaded(
                {"entries": [{"title": "Vid 1", "duration": 60, "uploader": "Chan"}]}
            )

        self.window.url_input.setText("https://www.youtube.com/watch?v=different")
        with patch.object(self.window, "run_yt_dlp", return_value=False) as run_mock:
            self.window.download_playlist()
            self.assertEqual(
                run_mock.call_args.kwargs["url"],
                "https://www.youtube.com/playlist?list=PL123",
            )
        status_item = self.window.playlist_table.item(0, 1)
        assert status_item is not None
        self.assertEqual(status_item.text(), "Pending")
        self.assertEqual(self.window.current_playlist_downloads, [])

    def test_is_valid_url_accepts_long_tlds_and_ipv6(self):
        for valid in (
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://video.example.network/watch?v=1",
            "https://example.youtube/clip",
            "http://[::1]:8080/video",
            "http://localhost:3000/test",
        ):
            with self.subTest(url=valid):
                self.assertTrue(self.window.is_valid_url(valid))
        for invalid in ("", "not-a-url", "ftp://example.com/file", "https://bad host/path"):
            with self.subTest(url=invalid):
                self.assertFalse(self.window.is_valid_url(invalid))

    def test_terminal_and_advanced_output_do_not_double_space(self):
        term = TerminalWindow()
        term.append("line 1\n")
        term.append("line 2\n")
        self.assertEqual(term.output.toPlainText(), "line 1\nline 2\n")
        term.close()
        term.deleteLater()

        self.window.advanced_output.clear()
        self.window.append_worker_output(self.window.advanced_output, "alpha\n")
        self.window.append_worker_output(self.window.advanced_output, "beta\n")
        self.assertEqual(self.window.advanced_output.toPlainText(), "alpha\nbeta\n")

    def test_progress_parsing_handles_approx_size_and_already_downloaded(self):
        worker = DownloadThread([], "https://www.youtube.com/watch?v=test")
        updates = []
        worker.progress.connect(lambda pct, status: updates.append((pct, status)))
        worker._parse_progress(  # pylint: disable=protected-access
            "[download]  42.5% of ~ 15.20MiB at  2.10MiB/s ETA 00:04"
        )
        worker._parse_progress(  # pylint: disable=protected-access
            "[download] video.mp4 has already been downloaded"
        )
        self.assertEqual(updates[0], (42, "of ~15.20MiB at 2.10MiB/s ETA 00:04"))
        self.assertEqual(updates[1], (100, "Download complete!"))

    def test_format_fetcher_extracts_stderr_error_detail(self):
        msg = FormatFetcher._extract_error_message(  # pylint: disable=protected-access
            "WARNING: something\nERROR: Private video. Sign in if you've been granted access\n"
        )
        self.assertEqual(msg, "Private video. Sign in if you've been granted access")

    def test_load_settings_handles_non_dict_json_gracefully(self):
        for item in self.patches:
            if item.attribute == "load_settings":
                item.stop()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "settings.json"
            cfg.write_text("[]", encoding="utf-8")
            self.window.config_file = cfg
            self.window.legacy_config_file = cfg
            self.window.load_settings()  # Should not raise AttributeError

    def test_vertical_shorts_labeled_by_short_side(self):
        self.assertEqual(
            self.window.extract_simple_format_display("137: 1080x1920 mp4", is_video=True),
            "1080p",
        )
        self.assertEqual(
            self.window.extract_simple_format_display("137: 1920x1080 mp4", is_video=True),
            "1080p",
        )

    def test_audio_only_specific_format_does_not_transcode_to_mp3(self):
        self.window.video_combo.clear()
        self.window.video_combo.addItem("No video (audio only)", "none")
        self.window.audio_combo.clear()
        self.window.audio_combo.addItem("140: m4a 128kbps [mp4a]", "140")
        selection = self.window.build_selected_download_args()
        assert selection is not None
        args, fmt_id, _ = selection
        self.assertEqual(fmt_id, "140")
        self.assertNotIn("-x", args)
        self.assertNotIn("--audio-format", args)

    def test_default_pre_analyze_fallback_uses_bv_ba_b(self):
        selection = self.window.build_selected_download_args()
        assert selection is not None
        args, fmt_id, display = selection
        self.assertEqual(fmt_id, "bv*+ba/b")
        self.assertEqual(display, "best")
        self.assertIn("bv*+ba/b", args)

    def test_compatibility_prefixed_node_and_short_ytdlp_date(self):
        self.assertTrue(is_supported_runtime("Node", "Node v22.14.0"))
        self.assertTrue(needs_ytdlp_update("2023.7.6"))

    def test_about_tab_refreshes_dirty_dependency_statuses(self):
        with (
            patch.object(self.window, "check_ytdlp_version") as check_ytdlp,
            patch.object(self.window, "check_ffmpeg_version") as check_ffmpeg,
            patch.object(self.window, "check_js_runtime_version") as check_js,
        ):
            self.window.mark_dependency_status_dirty()
            about_idx = self.window.tabs.indexOf(self.window.about_scroll_area)
            self.window.tabs.setCurrentIndex(about_idx)
            check_ytdlp.assert_called_once_with(show_warning=False, async_mode=True)
            check_ffmpeg.assert_called_once_with(async_mode=True)
            check_js.assert_called_once_with(async_mode=True)

    def test_async_ytdlp_probe_updates_label_off_main_thread(self):
        for item in self.patches:
            if item.attribute == "check_ytdlp_version":
                item.stop()
        fake_result = subprocess.CompletedProcess(
            args=["yt-dlp", "--version"], returncode=0, stdout="2026.10.26\n", stderr=""
        )
        with patch("yt_dlp_gui.probes.subprocess.run", return_value=fake_result):
            self.window.check_ytdlp_version(show_warning=False, async_mode=True)
            worker = self.window._probe_workers["ytdlp"]  # pylint: disable=protected-access
            self.assertIsNotNone(worker)
            self.assertTrue(worker.wait(3000))
            self.app.processEvents()

        self.assertEqual(self.window.ytdlp_version, "2026.10.26")
        self.assertIn("2026.10.26", self.window.ytdlp_version_label.text())

    def test_cancel_analyze_and_playlist_suppress_error_dialog(self):
        fake_fetcher = Mock(stop_requested=True)
        fake_fetcher.isRunning.return_value = True
        self.window.format_fetcher = fake_fetcher
        self.window.cancel_analyze_btn.setEnabled(True)

        self.window.cancel_analyze()
        fake_fetcher.stop.assert_called_once()
        self.assertFalse(self.window.cancel_analyze_btn.isEnabled())

        with (
            patch.object(self.window, "sender", return_value=fake_fetcher),
            patch("yt_dlp_gui.app.QMessageBox.critical") as critical,
        ):
            self.window.on_fetch_error("Cancelled")
            critical.assert_not_called()
        self.assertEqual(self.window.download_page_status_label.text(), "Analysis cancelled")

        fake_pl_fetcher = Mock(stop_requested=True)
        fake_pl_fetcher.isRunning.return_value = True
        self.window.playlist_fetcher = fake_pl_fetcher
        self.window.cancel_playlist_load()
        fake_pl_fetcher.stop.assert_called_once()

        with (
            patch.object(self.window, "sender", return_value=fake_pl_fetcher),
            patch("yt_dlp_gui.app.QMessageBox.critical") as critical,
        ):
            self.window.on_playlist_error("Cancelled")
            critical.assert_not_called()
        self.assertEqual(self.window.playlist_status_label.text(), "Playlist load cancelled")

    def test_cancel_advanced_command_stops_non_download_thread(self):
        fake_thread = Mock(is_download=False)
        fake_thread.isRunning.return_value = True
        self.window.download_thread = fake_thread
        self.window.cancel_advanced_btn.setEnabled(True)

        self.window.cancel_advanced_command()
        fake_thread.stop.assert_called_once()
        self.assertFalse(self.window.cancel_advanced_btn.isEnabled())

    def test_live_terminal_buffer_replays_when_opened_mid_run(self):
        self.window.append_terminal_output("line 1\n")
        self.window.append_terminal_output("line 2\n")
        self.window.toggle_terminal_output(2)  # Qt.CheckState.Checked
        term = self.window.terminal_window
        self.assertIsNotNone(term)
        assert term is not None
        self.assertEqual(term.output.toPlainText(), "line 1\nline 2\n")
        self.assertEqual(term.output.maximumBlockCount(), 5000)
        self.assertEqual(self.window.advanced_output.maximumBlockCount(), 5000)

        self.window.append_terminal_output("line 3\n")
        self.assertEqual(
            term.output.toPlainText(),
            "line 1\nline 2\nline 3\n",
        )
        term.clear()
        self.assertEqual(len(self.window._terminal_buffer), 0)  # pylint: disable=protected-access

    def test_terminate_process_tree_posix_and_windows(self):
        self.assertTrue(managed_subprocess_kwargs().get("start_new_session"))

        fake_proc = Mock(pid=4321)
        fake_proc.poll.return_value = None
        fake_proc.wait.side_effect = subprocess.TimeoutExpired("yt-dlp", 0.1)

        with (
            patch("yt_dlp_gui.process_utils.sys.platform", "linux"),
            patch("yt_dlp_gui.process_utils.os.killpg") as killpg,
        ):
            terminate_process_tree(fake_proc, force=True, timeout=0.1)
            self.assertEqual(killpg.call_count, 2)

        with (
            patch("yt_dlp_gui.process_utils.sys.platform", "win32"),
            patch("yt_dlp_gui.process_utils.hidden_subprocess_kwargs", return_value={}),
            patch("yt_dlp_gui.process_utils.subprocess.run") as run_mock,
        ):
            terminate_process_tree(fake_proc, force=True, timeout=1.0)
            self.assertEqual(
                run_mock.call_args.args[0],
                ["taskkill", "/T", "/F", "/PID", "4321"],
            )

    def test_hdr_label_and_output_container_audio_format_selectors(self):
        fake_fetcher = Mock(url="https://www.youtube.com/watch?v=hdr")
        self.window.format_fetcher = fake_fetcher
        payload = {
            "title": "HDR Video",
            "formats": [
                {
                    "format_id": "337",
                    "ext": "webm",
                    "vcodec": "vp9.2",
                    "acodec": "none",
                    "resolution": "3840x2160",
                    "height": 2160,
                    "fps": 60,
                    "dynamic_range": "HDR10",
                },
                {
                    "format_id": "251",
                    "ext": "webm",
                    "vcodec": "none",
                    "acodec": "opus",
                    "abr": 160,
                    "language": "en",
                },
            ],
        }
        with patch.object(self.window, "sender", return_value=fake_fetcher):
            self.window.on_formats_fetched(payload)

        video_text = self.window.video_combo.itemText(self.window.video_combo.findData("337"))
        audio_text = self.window.audio_combo.itemText(self.window.audio_combo.findData("251"))
        self.assertIn("[vp9]", video_text)
        self.assertIn("[HDR10]", video_text)
        self.assertIn("[opus]", audio_text)
        self.assertIn("[en]", audio_text)

        # MKV merge container
        self.window.video_container_combo.setCurrentIndex(
            self.window.video_container_combo.findData("mkv")
        )
        selection = self.window.build_selected_download_args()
        assert selection is not None
        args, _, _ = selection
        self.assertIn("--merge-output-format", args)
        self.assertIn("mkv", args)

        # Original merge container omits --merge-output-format
        self.window.video_container_combo.setCurrentIndex(
            self.window.video_container_combo.findData("original")
        )
        selection = self.window.build_selected_download_args()
        assert selection is not None
        args, _, _ = selection
        self.assertNotIn("--merge-output-format", args)

        # Audio-only with opus extraction
        self.window.video_combo.setCurrentIndex(self.window.video_combo.findData("none"))
        self.window.audio_format_combo.setCurrentIndex(
            self.window.audio_format_combo.findData("opus")
        )
        selection = self.window.build_selected_download_args()
        assert selection is not None
        args, _, _ = selection
        self.assertIn("-x", args)
        self.assertIn("opus", args)

    def test_abort_download_handles_thread_finishing_during_dialog(self):
        running_thread = Mock()
        running_thread.isRunning.return_value = True
        self.window.download_thread = running_thread

        def simulate_finish_during_prompt(*_args, **_kwargs):
            self.window.download_thread = None
            return QMessageBox.StandardButton.Yes

        with patch(
            "yt_dlp_gui.app.QMessageBox.question",
            side_effect=simulate_finish_during_prompt,
        ):
            self.window.abort_download()

        running_thread.stop.assert_not_called()

    def test_track_worker_thread_releases_and_deletes_on_finished(self):
        worker = FakeWorker()
        self.window.track_worker_thread(worker)
        self.assertIn(worker, self.window._worker_threads)  # pylint: disable=protected-access
        worker.finished.emit()
        self.assertNotIn(worker, self.window._worker_threads)  # pylint: disable=protected-access
        self.assertTrue(worker.deleted)


if __name__ == "__main__":
    unittest.main()
