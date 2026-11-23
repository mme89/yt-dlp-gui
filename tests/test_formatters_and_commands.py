"""Unit tests for formatters, CommandMixin, and background workers."""

import io
import json
import os
import unittest
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication

from yt_dlp_gui.commands import CommandMixin
from yt_dlp_gui.formatters import (
    extract_video_metadata,
    format_count,
    format_duration,
    format_filesize,
    format_upload_date,
    parse_video_formats,
)
from yt_dlp_gui.workers import DownloadThread, FormatFetcher


def qt_application():
    """Create one headless Qt application for worker signal tests."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


class FakeLineEdit:
    """Minimal QLineEdit stand-in for CommandMixin unit tests."""

    def __init__(self, text=""):
        self._text = text

    def text(self):
        """Return stored text."""
        return self._text


class FakeCombo:
    """Minimal QComboBox stand-in for CommandMixin unit tests."""

    def __init__(self, text="", data=""):
        self._text = text
        self._data = data

    def currentText(self):  # pylint: disable=invalid-name
        """Return current label."""
        return self._text

    def currentData(self):  # pylint: disable=invalid-name
        """Return current item data."""
        return self._data


class CommandHarness(CommandMixin):
    """Lightweight CommandMixin host without creating a QMainWindow."""

    def __init__(self):
        self.custom_options_input = FakeLineEdit()
        self.destination_input = FakeLineEdit("/tmp/downloads")
        self.limit_rate_input = FakeLineEdit()
        self.throttled_rate_input = FakeLineEdit()
        self.format_input = FakeLineEdit()
        self.video_combo = FakeCombo("Best video", "bestvideo")
        self.audio_combo = FakeCombo("Best audio", "bestaudio")
        self.video_container_combo = FakeCombo("MP4", "mp4")
        self.audio_format_combo = FakeCombo("Original", "original")
        self.format_data = {}
        self.js_args = []
        self.ffmpeg_path = "ffmpeg"
        self.subtitle_calls = []

    def get_js_runtime_args(self):
        """Return configured JS runtime args."""
        return list(self.js_args)

    def get_ffmpeg_path(self):
        """Return configured FFmpeg path."""
        return self.ffmpeg_path

    def add_subtitle_args(self, _args, *, embed=True):
        """Record subtitle embed flag."""
        self.subtitle_calls.append(embed)


class FormatterTests(unittest.TestCase):
    """Test pure formatting and yt-dlp payload parsing helpers."""

    def test_duration_filesize_count_and_date_formatters(self):
        self.assertEqual(format_duration(0), "Unknown")
        self.assertEqual(format_duration(None), "Unknown")
        self.assertEqual(format_duration(65), "1:05")
        self.assertEqual(format_duration(3661), "1:01:01")

        self.assertEqual(format_filesize(0, compact=True), "")
        self.assertEqual(format_filesize(0, compact=False), "Unknown")
        self.assertEqual(format_filesize(2048, compact=False), "2 KB")
        self.assertEqual(format_filesize(5 * 1024 * 1024, compact=True), "5.0MB")
        self.assertEqual(format_filesize(2 * 1024**3, compact=False), "2.0 GB")

        self.assertEqual(format_count(999), "999")
        self.assertEqual(format_count(1_500), "1.5K")
        self.assertEqual(format_count(2_500_000), "2.5M")

        self.assertEqual(format_upload_date("20261026"), "2026-10-26")
        self.assertEqual(format_upload_date("invalid"), "Unknown")

    def test_parse_video_formats_skips_invalid_entries_and_sorts_none_fields(self):
        formats = [
            None,
            {"ext": "mp4"},  # missing format_id
            {
                "format_id": "18",
                "ext": "mp4",
                "vcodec": "avc1.42001E",
                "acodec": "mp4a.40.2",
                "resolution": "640x360",
                "height": 360,
                "filesize_approx": 10 * 1024 * 1024,
            },
            {
                "format_id": "313",
                "ext": "webm",
                "vcodec": "vp9",
                "acodec": "none",
                "resolution": "3840x2160",
                "height": 2160,
                "fps": 60,
                "dynamic_range": "HDR10",
            },
            {
                "format_id": "sb0",
                "ext": "mhtml",
                "vcodec": "images",
                "acodec": "none",
                "height": None,
                "fps": None,
                "tbr": None,
            },
            {
                "format_id": "251",
                "ext": "webm",
                "vcodec": "none",
                "acodec": "opus",
                "abr": 160,
                "language": "en",
            },
            {
                "format_id": "139",
                "ext": "m4a",
                "vcodec": "none",
                "acodec": "mp4a",
                "abr": None,
            },
        ]
        video, audio, data = parse_video_formats(formats)
        self.assertEqual([fid for _, fid, _ in video], ["313", "18", "sb0"])
        self.assertEqual([fid for _, fid, _ in audio], ["251", "139"])
        self.assertIn("[HDR10]", video[0][0])
        self.assertIn("[video+audio]", video[1][0])
        self.assertIn("[en]", audio[0][0])
        self.assertIn("18", data)

    def test_extract_video_metadata_handles_missing_and_present_fields(self):
        meta = extract_video_metadata(
            {
                "title": "Sample",
                "duration": 125,
                "uploader": "Channel",
                "upload_date": "20260105",
                "view_count": 12500,
                "like_count": 500,
                "dislike_count": 0,
                "thumbnail": "https://i.ytimg.com/vi/abc/hqdefault.jpg",
            }
        )
        self.assertEqual(meta["title"], "Sample")
        self.assertEqual(meta["duration"], "2:05")
        self.assertEqual(meta["upload_date"], "2026-01-05")
        self.assertEqual(meta["views"], "12.5K views")
        self.assertEqual(meta["likes"], "👍 500")

        empty_meta = extract_video_metadata({})
        self.assertEqual(empty_meta["title"], "Unknown")
        self.assertEqual(empty_meta["likes"], "No data available")


class CommandMixinTests(unittest.TestCase):
    """Test CommandMixin argument building, validation, and size estimation."""

    def test_rate_limit_validation(self):
        harness = CommandHarness()
        harness.limit_rate_input = FakeLineEdit("4.2M")
        harness.throttled_rate_input = FakeLineEdit("100K")
        self.assertEqual(
            harness.get_rate_limit_args(),
            ["--limit-rate", "4.2M", "--throttled-rate", "100K"],
        )

        harness.limit_rate_input = FakeLineEdit("bad-value")
        with patch("yt_dlp_gui.commands.QMessageBox.warning") as warn:
            self.assertIsNone(harness.get_rate_limit_args())
            warn.assert_called_once()

    def test_build_ytdlp_args_ordering_and_newline_deduplication(self):
        harness = CommandHarness()
        harness.ffmpeg_path = "/opt/bin/ffmpeg"
        harness.custom_options_input = FakeLineEdit("--no-mtime --newline")
        harness.js_args = ["--js-runtimes", "deno:/usr/bin/deno"]
        harness.limit_rate_input = FakeLineEdit("2M")

        args = harness.build_ytdlp_args(["-f", "18"], is_download=True, output_template="out.mp4")
        self.assertEqual(
            args,
            [
                "--ffmpeg-location",
                "/opt/bin/ffmpeg",
                "-P",
                "/tmp/downloads",
                "--no-mtime",
                "--newline",
                "--js-runtimes",
                "deno:/usr/bin/deno",
                "-f",
                "18",
                "-o",
                "out.mp4",
                "--limit-rate",
                "2M",
            ],
        )

    def test_build_selected_download_args_rejects_both_none(self):
        harness = CommandHarness()
        harness.video_combo = FakeCombo("No video", "none")
        harness.audio_combo = FakeCombo("No audio", "none")
        with patch("yt_dlp_gui.commands.QMessageBox.warning") as warn:
            self.assertIsNone(harness.build_selected_download_args())
            warn.assert_called_once()

    def test_build_selected_download_args_respects_yes_playlist_override(self):
        harness = CommandHarness()
        harness.custom_options_input = FakeLineEdit("--yes-playlist")
        selection = harness.build_selected_download_args()
        assert selection is not None
        args, _, _ = selection
        self.assertNotIn("--no-playlist", args)

    def test_calculate_format_size_variants(self):
        harness = CommandHarness()
        harness.format_data = {
            "137": {"filesize": 40 * 1024 * 1024},
            "140": {"filesize_approx": 10 * 1024 * 1024},
            "251": {"filesize": 0},
        }
        self.assertEqual(harness.calculate_format_size("137+140"), "50 MB")
        self.assertEqual(harness.calculate_format_size("137+bestaudio"), "Partial")
        self.assertEqual(harness.calculate_format_size("bestvideo+bestaudio"), "Dynamic")
        self.assertEqual(harness.calculate_format_size("251"), "Unknown")


class DetailedWorkerTests(unittest.TestCase):
    """Test DownloadThread and FormatFetcher success, failure, and progress paths."""

    @classmethod
    def setUpClass(cls):
        cls.app = qt_application()

    def test_download_thread_streams_output_progress_and_exit_code(self):
        fake_proc = Mock()
        fake_proc.stdout = io.StringIO(
            "[download] Destination: clip.mp4\n"
            "[download]  50.0% of 20.00MiB at  4.00MiB/s ETA 00:02\n"
            "[Merger] Merging formats into \"clip.mp4\"\n"
            "[ExtractAudio] Destination: clip.mp3\n"
            "[EmbedSubtitle] Embedding subtitles in \"clip.mp4\"\n"
        )
        fake_proc.wait.return_value = 0

        worker = DownloadThread(["-f", "18"], "https://www.youtube.com/watch?v=abc")
        progress_events = []
        exit_codes = []
        worker.progress.connect(lambda pct, msg: progress_events.append((pct, msg)))
        worker.finished_signal.connect(exit_codes.append)

        with patch("yt_dlp_gui.workers.subprocess.Popen", return_value=fake_proc):
            worker.run()

        self.assertEqual(exit_codes, [0])
        self.assertEqual(progress_events[0], (0, "Starting download: clip.mp4"))
        self.assertEqual(progress_events[1], (50, "of 20.00MiB at 4.00MiB/s ETA 00:02"))
        self.assertEqual(progress_events[2], (100, "Merging video and audio..."))
        self.assertEqual(progress_events[3], (100, "Extracting audio..."))
        self.assertEqual(progress_events[4], (100, "Embedding subtitles..."))

    def test_format_fetcher_emits_parsed_json_and_handles_invalid_json(self):
        fake_ok = Mock(returncode=0)
        fake_ok.communicate.return_value = (json.dumps({"title": "Demo", "formats": []}), "")
        fetcher = FormatFetcher("https://www.youtube.com/watch?v=abc")
        results = []
        fetcher.finished.connect(results.append)
        with patch("yt_dlp_gui.workers.subprocess.Popen", return_value=fake_ok):
            fetcher.run()
        self.assertEqual(results, [{"title": "Demo", "formats": []}])

        fake_bad = Mock(returncode=0)
        fake_bad.communicate.return_value = ("not-json", "")
        bad_fetcher = FormatFetcher("https://www.youtube.com/watch?v=abc")
        errors = []
        bad_fetcher.error.connect(errors.append)
        with patch("yt_dlp_gui.workers.subprocess.Popen", return_value=fake_bad):
            bad_fetcher.run()
        self.assertEqual(len(errors), 1)

        fake_fail = Mock(returncode=1)
        fake_fail.communicate.return_value = ("", "ERROR: Video unavailable\n")
        fail_fetcher = FormatFetcher("https://www.youtube.com/watch?v=abc")
        fail_errors = []
        fail_fetcher.error.connect(fail_errors.append)
        with patch("yt_dlp_gui.workers.subprocess.Popen", return_value=fake_fail):
            fail_fetcher.run()
        self.assertEqual(fail_errors, ["Video unavailable"])


if __name__ == "__main__":
    unittest.main()
