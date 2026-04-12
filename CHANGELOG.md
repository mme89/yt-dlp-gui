# Changelog

All notable changes to this project will be documented in this file.

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
