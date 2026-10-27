"""Check published GUI releases without blocking the Qt event loop."""

import json
import re

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest


RELEASES_URL = "https://github.com/mme89/yt-dlp-gui/releases"
LATEST_RELEASE_API = "https://api.github.com/repos/mme89/yt-dlp-gui/releases/latest"
VERSION_PATTERN = re.compile(
    r"v?(\d+)\.(\d+)\.(\d+)"
    r"(?P<pre>[-.]?(?:alpha|beta|rc|preview|pre)[.-]?\d*)?"
    r"(?:\+[A-Za-z0-9.-]+)?",
    re.IGNORECASE,
)


def available_release(payload, current_version):
    """Return a newer stable release, comparing numeric versions rather than strings."""
    if not isinstance(payload, dict):
        raise ValueError("Invalid release response")
    if payload.get("draft") is True or payload.get("prerelease") is True:
        return None
    tag = payload.get("tag_name")
    latest = VERSION_PATTERN.fullmatch(tag) if isinstance(tag, str) else None
    current = VERSION_PATTERN.fullmatch(current_version)
    if not latest or latest.group("pre") or not current:
        raise ValueError("Unrecognized release version")
    latest_number = tuple(map(int, latest.group(1, 2, 3)))
    current_number = tuple(map(int, current.group(1, 2, 3)))
    if latest_number > current_number or (latest_number == current_number and current.group("pre")):
        # Build the link from our known repository instead of trusting a response URL.
        return tag, f"{RELEASES_URL}/tag/{tag}"
    return None


class UpdateChecker(QObject):
    """One bounded, asynchronous request at a time; failures are nonfatal."""

    finished = Signal(str, str, str)  # status (available/current/error), version, release URL

    def __init__(self, current_version, parent=None, manager=None):
        super().__init__(parent)
        self.current_version = current_version
        self.manager = manager if manager is not None else QNetworkAccessManager(self)
        self._reply = None
        self.timeout_timer = QTimer(self)
        self.timeout_timer.setSingleShot(True)
        self.timeout_timer.setInterval(15000)
        self.timeout_timer.timeout.connect(self._on_timeout)

    def check(self):
        """Start a public GitHub API request; ignore concurrent checks."""
        if self._reply is not None:
            return False
        request = QNetworkRequest(QUrl(LATEST_RELEASE_API))
        request.setRawHeader(b"Accept", b"application/vnd.github+json")
        request.setRawHeader(b"User-Agent", f"yt-dlp-gui/{self.current_version}".encode("ascii"))
        request.setRawHeader(b"X-GitHub-Api-Version", b"2026-03-10")
        request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy,
        )
        reply = self.manager.get(request)
        self._reply = reply
        reply.finished.connect(lambda: self._on_finished(reply))
        self.timeout_timer.start()
        return True

    def _on_timeout(self):
        self.cancel()
        self.finished.emit("error", "", "")

    def _on_finished(self, reply):
        if reply is not self._reply:
            return
        self._reply = None
        self.timeout_timer.stop()
        try:
            if (reply.error() != QNetworkReply.NetworkError.NoError
                    or reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute) != 200):
                self.finished.emit("error", "", "")
                return
            release = available_release(json.loads(bytes(reply.readAll())), self.current_version)
            if release:
                self.finished.emit("available", *release)
            else:
                self.finished.emit("current", self.current_version, "")
        except (ValueError, TypeError, UnicodeError):
            self.finished.emit("error", "", "")
        finally:
            reply.deleteLater()

    def cancel(self):
        """Abort outstanding work without notifying during application shutdown."""
        self.timeout_timer.stop()
        reply = self._reply
        self._reply = None
        if reply is not None:
            reply.abort()
            reply.deleteLater()
