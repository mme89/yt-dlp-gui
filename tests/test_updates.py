"""Offline release-check and notification regression tests."""

import json
import os
import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QNetworkReply
from PySide6.QtWidgets import QApplication, QMessageBox

from yt_dlp_gui.app import YtDlpGUI
from yt_dlp_gui.updates import LATEST_RELEASE_API, UpdateChecker, available_release


def release(tag='v1.5.0', **kwargs):
    """Build the public release fields used in a test response."""
    return {"tag_name": tag, "draft": False, "prerelease": False, **kwargs}


def qt_application():
    """Create one headless application for network and widget tests."""
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    return QApplication.instance() or QApplication([])


class FakeReply(QObject):
    """Minimal network reply that can complete or abort synchronously."""

    finished = Signal()

    def __init__(self, payload=None, status=200, error=QNetworkReply.NetworkError.NoError):
        super().__init__()
        self.body = json.dumps(payload).encode()
        self.status = status
        self.network_error = error
        self.aborted = False

    def error(self):
        """Return the simulated network error."""
        return self.network_error

    def attribute(self, _attribute):
        """Return the simulated HTTP status."""
        return self.status

    def readAll(self):
        """Match QNetworkReply's body-reading interface."""
        return self.body

    def abort(self):
        """Finish the reply as an aborted request would."""
        self.aborted = True
        self.finished.emit()


class ReleaseVersionTests(unittest.TestCase):
    """Check release filtering, version comparisons, and release links."""

    def test_version_comparison(self):
        for current, latest, expected in [
            ('1.4.0', 'v1.5.0', True), ('1.9.0', 'v1.10.0', True),
            ('1.4.0', 'v1.4.0', False), ('1.5.0', 'v1.4.0', False),
            ('1.5.0-rc.1', 'v1.5.0', True), ('1.6.0-beta1', 'v1.5.0', False),
            ('1.4.0+build1', 'v1.4.0', False), ('1.4.0', '1.5.0', True),
        ]:
            with self.subTest(current=current, latest=latest):
                self.assertEqual(bool(available_release(release(latest), current)), expected)

    def test_drafts_and_prereleases_are_ignored(self):
        for field in ('draft', 'prerelease'):
            payload = release()
            payload[field] = True
            self.assertIsNone(available_release(payload, '1.4.0'))

    def test_malformed_responses_are_errors(self):
        for payload in ([], None, {}, {'tag_name': 7}, release('v1.5.0-rc1'),
                        release('<a href="https://example.com">1.5.0</a>')):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                available_release(payload, '1.4.0')

    def test_release_link_uses_known_repository(self):
        _, url = available_release(release(html_url='https://example.com'), '1.4.0')
        self.assertEqual(url, 'https://github.com/mme89/yt-dlp-gui/releases/tag/v1.5.0')


class UpdateCheckerTests(unittest.TestCase):
    """Check asynchronous requests, failures, timeouts, and cancellation."""

    @classmethod
    def setUpClass(cls):
        cls.app = qt_application()

    def setUp(self):
        self.reply = FakeReply(release())
        self.manager = Mock()
        self.manager.get.return_value = self.reply
        self.checker = UpdateChecker('1.4.0', manager=self.manager)
        self.results = []
        self.checker.finished.connect(lambda *args: self.results.append(args))

    def tearDown(self):
        self.checker.cancel()
        self.checker.deleteLater()

    def test_async_request_and_new_release_result(self):
        self.assertTrue(self.checker.check())
        self.assertEqual(self.results, [])
        request = self.manager.get.call_args.args[0]
        self.assertEqual(request.url().toString(), LATEST_RELEASE_API)
        self.assertEqual(bytes(request.rawHeader('Accept')), b'application/vnd.github+json')
        self.assertFalse(self.checker.check())
        self.assertEqual(self.manager.get.call_count, 1)
        self.reply.finished.emit()
        self.assertEqual(self.results[0][0:2], ('available', 'v1.5.0'))
        self.assertFalse(self.checker.timeout_timer.isActive())

    def test_current_release(self):
        self.reply.body = json.dumps(release('v1.4.0')).encode()
        self.checker.check()
        self.reply.finished.emit()
        self.assertEqual(self.results, [('current', '1.4.0', '')])

    def test_http_errors_offline_and_bad_json(self):
        for status, error, body in [
            (403, QNetworkReply.NetworkError.NoError, b'{}'),
            (429, QNetworkReply.NetworkError.NoError, b'{}'),
            (200, QNetworkReply.NetworkError.HostNotFoundError, b'{}'),
            (200, QNetworkReply.NetworkError.NoError, b'not json'),
        ]:
            with self.subTest(status=status, error=error):
                self.reply.status, self.reply.network_error, self.reply.body = status, error, body
                self.assertTrue(self.checker.check())
                self.reply.finished.emit()
                self.assertEqual(self.results[-1], ('error', '', ''))

    def test_timeout_aborts_and_allows_retry(self):
        self.checker.check()
        self.checker.timeout_timer.timeout.emit()
        self.assertTrue(self.reply.aborted)
        self.assertEqual(self.results, [('error', '', '')])
        self.assertTrue(self.checker.check())

    def test_shutdown_aborts_without_notification(self):
        self.checker.check()
        self.checker.cancel()
        self.reply.finished.emit()
        self.assertTrue(self.reply.aborted)
        self.assertEqual(self.results, [])


class UpdateNotificationTests(unittest.TestCase):
    """Check update notifications and their lifecycle in the main window."""

    @classmethod
    def setUpClass(cls):
        cls.app = qt_application()

    def setUp(self):
        self.patches = [patch.object(YtDlpGUI, name) for name in (
            'load_settings', 'setup_settings_autosave', 'save_settings',
            'check_ytdlp_version', 'check_ffmpeg_version',
            'check_js_runtime_version', 'check_ytdlp_ejs_status',
        )]
        for item in self.patches:
            item.start()
        self.window = YtDlpGUI()
        self.window.update_startup_timer.stop()
        self.window.update_timer.stop()
        self.reply = FakeReply(release('v2.0.0'))
        self.window.update_checker.manager = Mock(get=Mock(return_value=self.reply))

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        for item in self.patches:
            item.stop()

    def test_notification_link_and_session_deduplication(self):
        self.window.check_for_updates()
        self.assertFalse(self.window.check_updates_button.isEnabled())
        self.reply.finished.emit()
        self.assertTrue(self.window.check_updates_button.isEnabled())
        self.assertIn('v2.0.0', self.window.update_status_label.text())
        notification = self.window.update_notification
        self.assertIsNotNone(notification)
        self.assertFalse(notification.isModal())
        with patch('yt_dlp_gui.app.QDesktopServices.openUrl') as open_url:
            notification.button(QMessageBox.StandardButton.Open).click()
            self.assertEqual(open_url.call_args.args[0].toString(),
                             'https://github.com/mme89/yt-dlp-gui/releases/tag/v2.0.0')
        self.window.check_for_updates()
        self.reply.finished.emit()
        self.assertIsNone(self.window.update_notification)

    def test_failed_check_can_be_retried_without_popup(self):
        self.reply.status = 403
        self.window.check_for_updates()
        self.reply.finished.emit()
        self.assertTrue(self.window.check_updates_button.isEnabled())
        self.assertIn('Could not check', self.window.update_status_label.text())
        self.assertIsNone(self.window.update_notification)
        self.reply.status = 200
        self.window.check_for_updates()
        self.reply.finished.emit()
        self.assertIsNotNone(self.window.update_notification)

    def test_close_cancels_request_and_timers(self):
        self.window.check_for_updates()
        self.window.close()
        self.assertTrue(self.reply.aborted)
        self.assertFalse(self.window.update_timer.isActive())
        self.assertFalse(self.window.update_startup_timer.isActive())
        self.assertIsNone(self.window.update_notification)


if __name__ == '__main__':
    unittest.main()
