"""Regression checks for external yt-dlp/runtime compatibility (no network needed)."""

import subprocess
import unittest
from types import MethodType, SimpleNamespace
from unittest.mock import Mock, patch

from yt_dlp_gui.app import YtDlpGUI
from yt_dlp_gui.compatibility import is_supported_runtime, needs_ytdlp_update


class RuntimeHarness:
    """Exercise runtime selection without creating a Qt window or user settings."""

    # Reuse the real detector while replacing its external dependencies.
    _detect_js_runtime = YtDlpGUI._detect_js_runtime  # pylint: disable=protected-access
    get_js_runtime_args = YtDlpGUI.get_js_runtime_args
    get_runtime_version = YtDlpGUI.get_runtime_version
    check_js_runtime_version = YtDlpGUI.check_js_runtime_version
    check_ytdlp_ejs_status = YtDlpGUI.check_ytdlp_ejs_status
    COLORS = YtDlpGUI.COLORS

    def __init__(self, versions=None, custom_args=None):
        self.versions = versions or {}
        self.custom_args = custom_args or []
        self.js_runtime_version_label = Mock()
        self.ytdlp_ejs_status_label = Mock()
        self.ytdlp_ejs_status = None

    def get_custom_options_args(self):
        """Return the configured test options."""
        return self.custom_args

    def find_available_executable(self, *names):
        """Resolve only executable names provided by the test fixture."""
        return next((f'/fake/{name}' for name in names if name in self.versions), None)

    def get_executable_version(
        self, executable_path, _version_args=("--version",), _success_codes=(0,)
    ):
        """Return fixture version text without launching a process."""
        return self.versions.get(executable_path.rsplit('/', 1)[-1])

    def detect_js_runtime(self, **_kwargs):
        """Recompute selection without caching fixture state."""
        return self._detect_js_runtime()


class CompatibilityTests(unittest.TestCase):
    """Check supported runtime boundaries, selection, and dependency status."""

    def test_runtime_boundaries(self):
        cases = [
            ('Deno', 'deno 2.2.9', False), ('Deno', 'deno 2.3.0 (stable)', True),
            ('Node', 'v20.19.2', False), ('Node', 'v22.0.0', True),
            ('Node', 'v24.1.0', True), ('Bun', '1.2.10', False),
            ('Bun', '1.2.11', True), ('Bun', '1.3.14', True),
            ('Bun', '1.3.15', False), ('Bun', '1.4.0', False),
            ('QuickJS', 'QuickJS version 2023-12-08', False),
            ('QuickJS', 'QuickJS version 2023-12-09', True),
            ('QuickJS', 'QuickJS-ng version 0.12.0', True),
            ('Node', None, False), ('Deno', 'unknown', False),
        ]
        for name, version, expected in cases:
            with self.subTest(name=name, version=version):
                self.assertEqual(is_supported_runtime(name, version), expected)

    def test_old_deno_falls_back_to_supported_node(self):
        harness = RuntimeHarness({'deno': 'deno 2.2.0', 'node': 'v22.0.0'})
        self.assertEqual(harness.get_js_runtime_args(), ['--js-runtimes', 'node:/fake/node'])

    def test_deno_is_preferred_and_passed_with_validated_path(self):
        harness = RuntimeHarness({'deno': 'deno 2.3.0', 'node': 'v22.0.0'})
        self.assertEqual(harness.get_js_runtime_args(), ['--js-runtimes', 'deno:/fake/deno'])

    def test_quickjs_precedes_bun(self):
        harness = RuntimeHarness({'qjs': 'QuickJS version 2025-04-26', 'bun': '1.3.14'})
        self.assertEqual(harness.detect_js_runtime()['name'], 'QuickJS')

    def test_unsupported_and_unreadable_runtimes_are_skipped(self):
        for versions in ({'node': 'v20.0.0', 'bun': '1.3.15'}, {'deno': None}, {}):
            with self.subTest(versions=versions):
                self.assertEqual(RuntimeHarness(versions).get_js_runtime_args(), [])

    def test_custom_settings_are_not_overridden(self):
        for options in (['--js-runtimes', 'node:/custom/node'],
                        ['--js-runtimes=bun'], ['--no-js-runtimes'],
                        ['--no-js-runtimes', '--js-runtimes', 'node']):
            with self.subTest(options=options):
                harness = RuntimeHarness({'deno': 'deno 2.3.0'}, options)
                self.assertEqual(harness.get_js_runtime_args(), [])
                self.assertEqual(harness.detect_js_runtime()['source'], 'custom')

    def test_custom_unsupported_version_warns(self):
        harness = RuntimeHarness({'node': 'v20.0.0'}, ['--js-runtimes', 'node'])
        harness.check_js_runtime_version()
        self.assertIn('Unsupported', harness.js_runtime_version_label.setText.call_args.args[0])
        self.assertIn(
            harness.COLORS['warning'],
            harness.js_runtime_version_label.setStyleSheet.call_args.args[0],
        )

    def test_bun_is_marked_deprecated(self):
        harness = RuntimeHarness({'bun': '1.3.14'})
        harness.check_js_runtime_version()
        self.assertIn('deprecated', harness.js_runtime_version_label.setText.call_args.args[0])

    def test_quickjs_uses_help_and_accepts_stderr(self):
        harness = RuntimeHarness()
        harness.get_executable_version = MethodType(YtDlpGUI.get_executable_version, harness)
        result = SimpleNamespace(
            returncode=1, stdout='', stderr='QuickJS version 2025-04-26\nusage...'
        )
        with patch('yt_dlp_gui.app.subprocess.run', return_value=result) as run:
            self.assertEqual(
                harness.get_runtime_version('QuickJS', '/fake/qjs'), 'QuickJS version 2025-04-26'
            )
            self.assertEqual(run.call_args.args[0], ['/fake/qjs', '--help'])
            self.assertEqual(run.call_args.kwargs['timeout'], 3)

    def test_nonzero_version_probe_is_rejected_for_node(self):
        result = SimpleNamespace(returncode=1, stdout='v22.0.0', stderr='')
        with patch('yt_dlp_gui.app.subprocess.run', return_value=result):
            self.assertIsNone(YtDlpGUI.get_executable_version(None, '/fake/node'))

    def test_probe_failure_is_not_selected(self):
        for error in (OSError('missing'), subprocess.TimeoutExpired('node', 3)):
            with self.subTest(error=error), patch(
                'yt_dlp_gui.app.subprocess.run', side_effect=error
            ):
                self.assertIsNone(YtDlpGUI.get_executable_version(None, '/fake/node'))

    def test_ejs_status_does_not_claim_external_package_availability(self):
        harness = RuntimeHarness()
        harness.check_ytdlp_ejs_status()
        self.assertEqual(harness.ytdlp_ejs_status, 'Not verified')
        self.assertIn(
            'yt-dlp installation', harness.ytdlp_ejs_status_label.setText.call_args.args[0]
        )

    def test_dated_release_comparison(self):
        for version, expected in [('2026.06.09', True), ('2026.10.21', True),
                                  ('2026.10.25.123456', True), ('2026.10.26', False),
                                  ('2026.10.26.123456', False), ('2027.01.01', False),
                                  ('custom-build', False)]:
            with self.subTest(version=version):
                self.assertEqual(needs_ytdlp_update(version), expected)


if __name__ == '__main__':
    unittest.main()
