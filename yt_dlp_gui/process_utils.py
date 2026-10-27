"""Platform-specific subprocess options for launching tools from the GUI."""

import subprocess
import sys


def hidden_subprocess_kwargs():
    """Return subprocess options that hide child console windows on Windows."""
    if sys.platform != "win32":
        return {}

    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW")}
