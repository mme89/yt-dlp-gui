# Changelog

All notable changes to this project will be documented in this file.

## [1.5.0] - 2026-10-27

### Added
- Check for new stable GUI releases in the background after startup and every seven days while running
- Notify users when a newer GUI release is available, with a link to its release page for manual download
- Add a "Check for Updates" button and update status to the About tab
- Handle offline connections, API errors, and timeouts without interrupting downloads, and cancel pending checks during shutdown

### Changed
- Add shared Qt-aware Pylint configuration and development setup instructions, replacing repeated signal exclusions and broad import/member suppressions
- Clean up test fixtures, module documentation, and format-size/runtime helpers
- Validate JavaScript runtime versions before automatic selection, prefer QuickJS over deprecated Bun, and show unsupported or unverified custom runtimes accurately
- Respect custom `--no-js-runtimes` options without automatically enabling another runtime
- Recommend yt-dlp 2026.10.26 or newer and document Python 3.11+ and Windows 10+ requirements for current yt-dlp installations
- Update pip installation guidance to include yt-dlp's default dependencies and EJS scripts

### Fixed
- Stop reporting EJS as installed or missing based on the GUI's Python environment, which does not describe the external yt-dlp installation
- Read QuickJS versions from help output and bound runtime version probes with a timeout

## [1.4.0] - 2026-06-14

### Added
- Added a shared `yt_dlp_gui/version.py` version source used by the app, build specs, and release validation
- Added Windows executable version metadata generated from the shared app version
- Added pinned release-build constraints for more reproducible GitHub Actions builds
- Added GitHub Actions validation to ensure release tags match the app version
- Added prerelease detection for alpha, beta, rc, preview, and pre release tags

### Changed
- Refactored the monolithic launcher into an importable `yt_dlp_gui` package with separate app, command, worker, terminal, process, and version modules
- Packaged builds now store settings in the platform user config directory instead of writing inside the bundled app or PyInstaller extraction directory
- Hardened release builds with read-only default workflow permissions, per-ref concurrency, 30-minute job timeouts, and an arm64 macOS runner
- macOS package metadata now reads the shared app version and advertises macOS 13.0 or newer
- Disabled UPX compression for macOS and Linux PyInstaller builds for better packaged-app reliability
- Added `PySide6.QtNetwork` to all PyInstaller hidden-import lists for build-spec parity
- Cleaned Linux build spec options by removing Windows-only Analysis settings

### Fixed
- Prevented Windows console windows from appearing when the GUI runs `yt-dlp`, `ffmpeg`, or related subprocess checks
- Migrated legacy `settings.json` data into the persistent app config location for packaged builds
- Updated the sample settings file to include the auto-captions setting

## [1.3.1] - 2026-04-12

### Changed
- Updated GitHub Actions workflow to Node 24-ready action versions
- Disabled UPX and strip in the Windows PyInstaller build to avoid packaged Python DLL load failures

### Fixed
- Abort button now keeps a readable width during downloads, including on Windows with scaling
- Hardened download/fetch shutdown cleanup to reduce abort-and-close crashes
- Reduced Qt/PySide teardown issues by simplifying worker output handling and explicit app-exit cleanup

## [1.3.0] - 2026-04-12

### Added
- About page status for JavaScript runtime detection used by yt-dlp
- About page status for `yt-dlp-ejs` availability in the current Python environment
- Subtitle option to include live chat when downloading all subtitles
- Subtitle option to keep separate subtitle files in addition to embedding them
- Helper text explaining default subtitle embedding behavior

### Changed
- Updated yt-dlp metadata fetch to use `--print "%()j"` instead of `--print-json`
- Updated subtitle listing to use `--print automatic_captions_table --print subtitles_table`
- Replaced deprecated subtitle option aliases with current yt-dlp forms
- Auto-detect supported JavaScript runtimes for yt-dlp, preferring configured or available runtimes
- "All subtitles" now excludes live chat by default unless explicitly enabled
- Subtitle downloads now embed subtitles by default and only keep subtitle files when requested

## [1.2.0] - 2025-11-12

### Added
- QtNetwork-based thumbnail loading for better PyInstaller compatibility
- Debug output for thumbnail loading errors

### Changed
- Switched from urllib to PySide6.QtNetwork for thumbnail downloads
- Improved thumbnail loading reliability in built applications

### Fixed
- Download progress bar and status now properly reset when clicking "Analyze" for a new video
- Thumbnail loading now works correctly in PyInstaller-built applications
- "Show auto-generated captions" checkbox now properly filters subtitle dropdown
- Auto-generated captions only appear when checkbox is enabled
- Subtitle dropdown refreshes immediately when toggling auto-captions checkbox
- PySide6.QtNetwork no longer excluded from build specs

## [1.1.0] - 2025-01-11

### Added
- Application logo in About tab and window icon
- Auto-generated subtitle/caption support with toggle option in settings
- "No audio" and "No video" options for video-only or audio-only downloads
- Platform-specific installation instructions for yt-dlp
- Cross-platform executable finder (searches common installation paths)
- Default download location set to ~/Downloads if not configured

### Changed
- Subtitle dropdown now shows both manual subtitles and auto-generated captions (when enabled)
- Manual subtitles marked with "(manual)", auto-captions marked with "(auto)"
- Improved dropdown arrow styling (removed custom CSS triangle)

### Fixed
- Built apps now find yt-dlp and ffmpeg in common installation locations
- Downloads no longer go to random directories when destination not set

## [1.0.1] - 2025-11-11

### Added
- Initial release of yt-dlp GUI
- Cross-platform support (Windows, macOS, Linux)
- Video format selection with quality options
- Audio format selection
- Subtitle download support
- Download queue management
- Playlist download support
- Terminal output window
- Custom format string input

### Technical
- Built with Python 3.13 and PySide6
- Optimized build sizes with excluded unused modules
- macOS builds optimized for Apple Silicon (arm64)

### Downloads
- **Windows**: `yt-dlp-gui-v1.0.0-windows.zip`
- **macOS**: `yt-dlp-gui-v1.0.0-mac.zip` (Apple Silicon optimized)
- **Linux**: `yt-dlp-gui-v1.0.0-linux.tar.gz`

### Installation
- **macOS**: Extract and drag `yt-dlp-gui.app` to Applications folder
- **Windows**: Extract and run `yt-dlp-gui.exe`
- **Linux**: Extract and run the `yt-dlp-gui` executable

### Requirements
- yt-dlp must be installed and available in PATH
- ffmpeg recommended for format conversion
