"""Compatibility requirements for the external yt-dlp installation and runtimes."""

import re


RECOMMENDED_YTDLP_VERSION = "2026.10.26"


def is_supported_runtime(name: str, version_line: str | None) -> bool:
    """Reject unknown versions instead of automatically selecting an unusable runtime."""
    if not version_line:
        return False
    if name == "QuickJS":
        if re.search(r"QuickJS[- ]ng\b", version_line, re.IGNORECASE):
            return True
        match = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", version_line)
        return bool(match and tuple(map(int, match.groups())) >= (2023, 12, 9))

    match = re.search(r"\b(\d+)\.(\d+)\.(\d+)\b", version_line)
    # Node prints a leading v, which is a word character.
    if not match:
        match = re.match(r"v(\d+)\.(\d+)\.(\d+)\b", version_line)
    if not match:
        return False
    version = tuple(map(int, match.groups()))
    if name == "Deno":
        return version >= (2, 3, 0)
    if name == "Node":
        return version >= (22, 0, 0)
    if name == "Bun":
        return (1, 2, 11) <= version <= (1, 3, 14)
    return False


def needs_ytdlp_update(version: str) -> bool:
    """Compare dated releases, including nightly versions with a dated prefix."""
    match = re.match(r"^(\d{4})\.(\d{2})\.(\d{2})(?:\D|$)", version)
    if not match:
        return False
    return tuple(map(int, match.groups())) < tuple(map(int, RECOMMENDED_YTDLP_VERSION.split('.')))
