# yt-dlp GUI

[![GitHub release](https://img.shields.io/github/v/release/mme89/yt-dlp-gui?label=Latest%20Release&style=for-the-badge)](https://github.com/mme89/yt-dlp-gui/releases/latest)
[![GitHub downloads](https://img.shields.io/github/downloads/mme89/yt-dlp-gui/total?label=Total%20Downloads&style=for-the-badge)](https://github.com/mme89/yt-dlp-gui/releases)
[![License](https://img.shields.io/github/license/mme89/yt-dlp-gui?style=for-the-badge)](https://github.com/mme89/yt-dlp-gui/blob/main/LICENSE)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-blue?style=for-the-badge)](https://github.com/mme89/yt-dlp-gui)

A modern, cross-platform GUI wrapper for [yt-dlp](https://github.com/yt-dlp/yt-dlp). This application provides an easy-to-use graphical interface for downloading videos without using the command line.

## Screenshots

<div align="center">
  <img src="screenshots/main-window.png" alt="Main Window" width="800">
  <p><em>Main download interface with format selection</em></p>
</div>

<div align="center">
  <img src="screenshots/playlist-view.png" alt="Playlist View" width="800">
  <p><em>Playlist management with selective downloads</em></p>
</div>

<div align="center">
  <img src="screenshots/queue-management.png" alt="Queue Management" width="800">
  <p><em>Download queue for batch processing</em></p>
</div>

## Features

- 🎥 Download videos from YouTube
- 🎨 Clean, modern interface with cross-platform styling
- 📊 Format selection with detailed information (resolution, codec, file size)
- 📝 Subtitle support (auto-generated and manual)
- 📋 Download queue management
- 🎵 Playlist support with selective downloads
- 🖼️ Video thumbnail preview
- 📈 Real-time download progress tracking
- ⚙️ Advanced options and custom arguments
- 🪟 Separate terminal window for detailed output

## Requirements

This application requires [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [FFmpeg](https://github.com/FFmpeg/FFmpeg) to be installed on your system.

- Use **yt-dlp 2026.10.26 or newer** for the latest bundled dependency security fixes. The GUI uses your separately installed yt-dlp; updating the GUI does not update yt-dlp.
- Python installations of current yt-dlp require **Python 3.11+**. Official Windows yt-dlp binaries require **Windows 10 or newer**. Pre-built GUI applications do not require a separate Python installation.
- Full YouTube support also requires EJS challenge solver scripts and a supported JavaScript runtime. Prefer **Deno 2.3+** or **Node.js 22+**. QuickJS 2023-12-09+ and all QuickJS-NG versions are supported. Bun is deprecated and supported only from 1.2.11 through 1.3.14.

The GUI automatically selects a supported runtime in this order: Deno, Node.js, QuickJS, then Bun. Unsupported or unrecognized versions are skipped. Explicit `--js-runtimes` and `--no-js-runtimes` custom options take precedence.

Official yt-dlp binaries already bundle EJS. For pip installations, install or upgrade yt-dlp and its default dependencies in the Python environment that runs yt-dlp:

```bash
python -m pip install -U "yt-dlp[default]"
```

For package-manager installations, upgrade through that package manager and check whether it includes EJS. The About tab does not verify EJS in the external yt-dlp installation; installing EJS into the GUI's Python environment alone may have no effect.

See the [yt-dlp EJS setup guide](https://github.com/yt-dlp/yt-dlp/wiki/EJS) and [2026.10.26 release notes](https://github.com/yt-dlp/yt-dlp/releases/tag/2026.10.26). If you suspect interception of your network traffic, upstream recommends manually replacing older official executables instead of using their self-updater.


## Installation

### Option 1: Download Pre-built Application (Recommended)

Download the latest release for your platform from the [Releases](https://github.com/mme89/yt-dlp-gui/releases) page:

- **macOS**: Download `yt-dlp-gui-mac.zip`, extract, and run the `.app`
- **Windows**: Download `yt-dlp-gui-windows.zip`, extract, and run the `.exe`
- **Linux**: Download `yt-dlp-gui-linux.tar.gz`, extract, and run the executable

### Option 2: Run from Source

1. Clone this repository:
```bash
git clone https://github.com/mme89/yt-dlp-gui.git
cd yt-dlp-gui
```

2. With Python 3.11 or newer, install the GUI dependencies (yt-dlp and FFmpeg must also be installed as described above):
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python yt-dlp-gui.py
```

### Option 3: Build Standalone Application

If you want to create your own standalone executable:

**macOS:**
```bash
pyinstaller build-specs/yt-dlp-gui-mac.spec
```

**Windows:**
```bash
pyinstaller build-specs/yt-dlp-gui-windows.spec
```

**Linux:**
```bash
pyinstaller build-specs/yt-dlp-gui-linux.spec
```

The built application will be in the `dist/` folder.

## Usage

### Basic Workflow

1. Paste a YouTube URL in the input field
2. Click "Analyze" to fetch available formats
3. Select your preferred video and audio formats
4. Choose download location in the Options tab
5. Click "Download Now" or "Add to Queue"

### Features Guide

- **Download Tab**: Select formats and download individual videos
- **Queue Tab**: Manage multiple downloads sequentially
- **Playlist Tab**: Load and download entire playlists with quality presets
- **Advanced Tab**: Add custom yt-dlp arguments
- **Options Tab**: Configure download paths and yt-dlp location

## Configuration

Settings are automatically saved to `settings.json` in the application directory, including:
- Download path
- yt-dlp executable path
- Window preferences

## Troubleshooting

**"yt-dlp not found"**
- Ensure yt-dlp is installed and in your PATH
- Or specify the full path in Options → yt-dlp Path

**"FFmpeg not found"**
- Install FFmpeg and ensure it's in your PATH
- Required for merging separate video/audio streams

**Format fetching fails**
- Check your internet connection
- Verify the URL is valid
- Some videos may have region restrictions

## Note

This project was created with the assistance of AI to provide a user-friendly interface for yt-dlp.

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.
