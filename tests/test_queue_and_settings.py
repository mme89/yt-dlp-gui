"""Tests for queue state transitions and settings persistence/migration."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication, QMessageBox

from yt_dlp_gui.app import YtDlpGUI


def qt_application():
    """Create one headless Qt application for window tests."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


class QueueAndSettingsTests(unittest.TestCase):
    """Verify queue lifecycle transitions and settings save/load/migration."""

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

    def test_queue_state_transitions_completed_failed_and_aborted(self):
        self.window.download_queue = [
            {
                "url": "https://www.youtube.com/watch?v=1",
                "args": ["-f", "18"],
                "format": "18",
                "format_display": "360p",
                "title": "First",
                "size": "5 MB",
                "status": "Pending",
            },
            {
                "url": "https://www.youtube.com/watch?v=2",
                "args": ["-f", "18"],
                "format": "18",
                "format_display": "360p",
                "title": "Second",
                "size": "6 MB",
                "status": "Pending",
            },
            {
                "url": "https://www.youtube.com/watch?v=3",
                "args": ["-f", "18"],
                "format": "18",
                "format_display": "360p",
                "title": "Third",
                "size": "7 MB",
                "status": "Pending",
            },
        ]
        self.window.update_queue_table()

        fake_threads = [
            Mock(stop_requested=False),
            Mock(stop_requested=False),
            Mock(stop_requested=True),
        ]
        started_urls = []

        def fake_run_queue(_args, url, _fmt=""):
            started_urls.append(url)
            self.window.download_thread = fake_threads[len(started_urls) - 1]
            return True

        with (
            patch.object(self.window, "run_yt_dlp_queue", side_effect=fake_run_queue),
            patch("yt_dlp_gui.queue_controller.QMessageBox.information") as info_box,
        ):
            self.window.start_queue_processing()
            self.assertTrue(self.window.is_processing_queue)
            self.assertEqual(self.window.download_queue[0]["status"], "Downloading")

            with patch.object(self.window, "sender", return_value=fake_threads[0]):
                self.window.on_queue_download_finished(0)
            self.assertEqual(self.window.download_queue[0]["status"], "Completed")
            self.assertEqual(self.window.download_queue[1]["status"], "Downloading")

            with patch.object(self.window, "sender", return_value=fake_threads[1]):
                self.window.on_queue_download_finished(1)
            self.assertEqual(self.window.download_queue[1]["status"], "Failed")
            self.assertEqual(self.window.download_queue[2]["status"], "Downloading")

            with patch.object(self.window, "sender", return_value=fake_threads[2]):
                self.window.on_queue_download_finished(-15)
            self.assertEqual(self.window.download_queue[2]["status"], "Aborted")
            self.assertFalse(self.window.is_processing_queue)
            info_box.assert_called_once()

        self.assertIn("Aborted: 1", self.window.queue_status_label.text())
        self.assertFalse(self.window.start_queue_btn.isEnabled())

    def test_stop_queue_processing_resets_current_item_to_pending(self):
        active_thread = Mock()
        active_thread.isRunning.return_value = True
        item = {
            "url": "https://www.youtube.com/watch?v=1",
            "args": ["-f", "18"],
            "format": "18",
            "format_display": "360p",
            "title": "Active",
            "size": "5 MB",
            "status": "Downloading",
        }
        self.window.download_queue = [item]
        self.window.is_processing_queue = True
        self.window.current_queue_item = item
        self.window.download_thread = active_thread

        with patch(
            "yt_dlp_gui.queue_controller.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            self.window.stop_queue_processing()

        self.assertFalse(self.window.is_processing_queue)
        self.assertEqual(item["status"], "Pending")
        active_thread.stop.assert_called_once()

    def test_remove_selected_from_queue_blocks_downloading_and_removes_pending(self):
        self.window.download_queue = [
            {
                "url": "https://www.youtube.com/watch?v=1",
                "args": ["-f", "18"],
                "format": "18",
                "format_display": "360p",
                "title": "Active",
                "size": "5 MB",
                "status": "Downloading",
            },
            {
                "url": "https://www.youtube.com/watch?v=2",
                "args": ["-f", "18"],
                "format": "18",
                "format_display": "360p",
                "title": "Waiting",
                "size": "5 MB",
                "status": "Pending",
            },
        ]
        self.window.update_queue_table()

        self.window.queue_table.selectRow(0)
        with patch("yt_dlp_gui.queue_controller.QMessageBox.warning") as warn:
            self.window.remove_selected_from_queue()
            warn.assert_called_once()
        self.assertEqual(len(self.window.download_queue), 2)

        self.window.queue_table.selectRow(1)
        with patch(
            "yt_dlp_gui.queue_controller.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            self.window.remove_selected_from_queue()
        self.assertEqual(len(self.window.download_queue), 1)
        self.assertEqual(self.window.download_queue[0]["title"], "Active")

    def test_settings_round_trip_and_legacy_migration(self):
        for item in self.patches:
            if item.attribute in ("load_settings", "save_settings"):
                item.stop()

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            legacy_cfg = tmp / "legacy.json"
            new_cfg = tmp / "config" / "settings.json"

            legacy_payload = {
                "destination": "/tmp/vids",
                "ytdlp_path": "/usr/local/bin/yt-dlp",
                "ffmpeg_path": "/usr/local/bin/ffmpeg",
                "custom_options": "--no-mtime",
                "limit_rate": "5M",
                "throttled_rate": "100K",
                "show_auto_captions": True,
                "video_container": "mkv",
                "audio_format": "opus",
            }
            legacy_cfg.write_text(json.dumps(legacy_payload), encoding="utf-8")

            self.window.legacy_config_file = legacy_cfg
            self.window.config_file = new_cfg
            self.window.load_settings()

            self.assertTrue(new_cfg.exists())
            self.assertEqual(self.window.destination_input.text(), "/tmp/vids")
            self.assertEqual(self.window.ytdlp_path_input.text(), "/usr/local/bin/yt-dlp")
            self.assertEqual(self.window.ffmpeg_path_input.text(), "/usr/local/bin/ffmpeg")
            self.assertEqual(self.window.custom_options_input.text(), "--no-mtime")
            self.assertEqual(self.window.limit_rate_input.text(), "5M")
            self.assertEqual(self.window.throttled_rate_input.text(), "100K")
            self.assertTrue(self.window.show_auto_captions_checkbox.isChecked())
            self.assertEqual(self.window.video_container_combo.currentData(), "mkv")
            self.assertEqual(self.window.audio_format_combo.currentData(), "opus")

            # Modify and save back to disk
            self.window.destination_input.setText("/tmp/updated")
            self.window.audio_format_combo.setCurrentIndex(
                self.window.audio_format_combo.findData("m4a")
            )
            self.window.save_settings(show_feedback=False)
            saved = json.loads(new_cfg.read_text(encoding="utf-8"))
            self.assertEqual(saved["destination"], "/tmp/updated")
            self.assertEqual(saved["audio_format"], "m4a")


if __name__ == "__main__":
    unittest.main()
