# Changelog

All notable changes to this project will be documented in this file.

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
