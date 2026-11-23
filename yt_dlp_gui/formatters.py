"""Pure formatting and metadata/format-parsing helpers for yt-dlp JSON payloads."""

from typing import Any


def format_duration(duration: Any) -> str:
    """Format a duration in seconds as M:SS or H:MM:SS."""
    if not duration:
        return "Unknown"
    hours = int(duration // 3600)
    minutes = int((duration % 3600) // 60)
    seconds = int(duration % 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def format_filesize(size_bytes: Any, *, compact: bool = True) -> str:
    """Format a byte count into KB/MB/GB strings."""
    if not size_bytes:
        return "" if compact else "Unknown"
    sep = "" if compact else " "
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / (1024**3):.1f}{sep}GB"
    if size_bytes >= 1024 * 1024:
        precision = 1 if compact else 0
        return f"{size_bytes / (1024**2):.{precision}f}{sep}MB"
    precision = 1 if compact else 0
    return f"{size_bytes / 1024:.{precision}f}{sep}KB"


def format_count(count: Any) -> str:
    """Format a numeric count using compact K/M suffixes."""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}K"
    return str(count)


def format_upload_date(upload_date: Any) -> str:
    """Format a yt-dlp YYYYMMDD upload date string as YYYY-MM-DD."""
    if isinstance(upload_date, str) and len(upload_date) == 8:
        return f"{upload_date[0:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
    return "Unknown"


FormatEntry = tuple[str, str, dict[str, Any]]


def parse_video_formats(
    formats: Any,
) -> tuple[list[FormatEntry], list[FormatEntry], dict[str, dict[str, Any]]]:
    """Parse and sort yt-dlp format dicts into video/muxed and audio display lists."""
    video_formats: list[tuple[str, str, dict[str, Any]]] = []
    audio_formats: list[tuple[str, str, dict[str, Any]]] = []
    format_data: dict[str, dict[str, Any]] = {}

    for fmt in formats or []:
        if not isinstance(fmt, dict):
            continue
        format_id = fmt.get("format_id") or ""
        if not format_id:
            continue

        ext = fmt.get("ext") or ""
        vcodec = fmt.get("vcodec") or "none"
        acodec = fmt.get("acodec") or "none"
        resolution = fmt.get("resolution") or "audio only"
        fps = fmt.get("fps") or 0
        abr = fmt.get("abr") or 0
        filesize = fmt.get("filesize") or fmt.get("filesize_approx") or 0
        size_str = format_filesize(filesize, compact=True)
        size_part = f" ({size_str})" if size_str else ""

        format_data[format_id] = fmt

        if vcodec != "none":
            fps_str = f" {fps}fps" if fps else ""
            codec_short = vcodec.split(".")[0]
            codec_part = f" [{codec_short}]" if codec_short and codec_short != "none" else ""
            dynamic_range = fmt.get("dynamic_range") or ""
            hdr_part = (
                f" [{dynamic_range}]"
                if dynamic_range and dynamic_range.upper() != "SDR"
                else ""
            )
            muxed_tag = " [video+audio]" if acodec != "none" else ""
            label = (
                f"{format_id}: {resolution} {ext}{fps_str}"
                f"{codec_part}{hdr_part}{muxed_tag}{size_part}"
            )
            video_formats.append((label, format_id, fmt))
        elif acodec != "none":
            abr_str = f"{abr}kbps" if abr else "unknown bitrate"
            codec_short = acodec.split(".")[0]
            codec_part = f" [{codec_short}]" if codec_short and codec_short != "none" else ""
            lang = fmt.get("language") or ""
            lang_part = f" [{lang}]" if lang else ""
            label = f"{format_id}: {ext} {abr_str}{codec_part}{lang_part}{size_part}"
            audio_formats.append((label, format_id, fmt))

    video_formats.sort(
        key=lambda x: (
            x[2].get("height") or 0,
            x[2].get("fps") or 0,
            x[2].get("tbr") or 0,
        ),
        reverse=True,
    )
    audio_formats.sort(
        key=lambda x: (x[2].get("abr") or 0, x[2].get("tbr") or 0),
        reverse=True,
    )
    return video_formats, audio_formats, format_data


def extract_video_metadata(data: dict[str, Any]) -> dict[str, str]:
    """Extract display-ready video metadata fields from a yt-dlp -J dictionary."""
    view_count = data.get("view_count") or 0
    like_count = data.get("like_count", 0)
    dislike_count = data.get("dislike_count", 0)

    views_str = f"{format_count(view_count)} views" if view_count else "Unknown"

    likes_parts = []
    if like_count:
        likes_parts.append(f"👍 {format_count(like_count)}")
    if dislike_count:
        likes_parts.append(f"👎 {format_count(dislike_count)}")

    if likes_parts:
        likes_str = " | ".join(likes_parts)
    elif like_count == 0 and dislike_count == 0:
        likes_str = "No data available"
    else:
        likes_str = "Unknown"

    return {
        "title": data.get("title") or "Unknown",
        "duration": format_duration(data.get("duration") or 0),
        "uploader": data.get("uploader") or "Unknown",
        "upload_date": format_upload_date(data.get("upload_date") or ""),
        "views": views_str,
        "likes": likes_str,
        "thumbnail": data.get("thumbnail") or "",
    }
