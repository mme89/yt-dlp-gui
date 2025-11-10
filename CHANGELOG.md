# Changelog

All notable changes to this project will be documented in this file.

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
