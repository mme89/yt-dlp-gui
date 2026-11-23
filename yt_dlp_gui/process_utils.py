"""Platform-specific subprocess options and process-tree cleanup helpers."""

import os
import signal
import subprocess
import sys


def hidden_subprocess_kwargs():
    """Return subprocess options that hide child console windows on Windows."""
    if sys.platform != "win32":
        return {}

    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW")}


def managed_subprocess_kwargs():
    """Return subprocess options for worker processes whose child trees may be terminated."""
    kwargs = hidden_subprocess_kwargs()
    if sys.platform != "win32":
        kwargs["start_new_session"] = True
    return kwargs


def terminate_process_tree(process, *, force=False, timeout=1.5):
    """Terminate a subprocess and any child processes it spawned (e.g. ffmpeg)."""
    if process is None or process.poll() is not None:
        return

    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(process.pid)],
                capture_output=True,
                check=False,
                timeout=max(1.0, timeout),
                **hidden_subprocess_kwargs(),
            )
        except (OSError, subprocess.SubprocessError):
            try:
                process.terminate()
                if force:
                    try:
                        process.wait(timeout=timeout)
                    except subprocess.TimeoutExpired:
                        process.kill()
            except (OSError, subprocess.SubprocessError):
                pass
        return

    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        try:
            process.terminate()
        except (OSError, subprocess.SubprocessError):
            return

    if force:
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                try:
                    process.kill()
                except (OSError, subprocess.SubprocessError):
                    pass
