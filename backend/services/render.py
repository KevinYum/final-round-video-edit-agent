"""Render the current timeline to a single video file using MoviePy."""

import logging
import re
from pathlib import Path

from moviepy import (
    ColorClip,
    CompositeVideoClip,
    TextClip,
    VideoFileClip,
    concatenate_videoclips,
)

logger = logging.getLogger(__name__)

# Font discovery — try common paths, fall back to name
_FONT_CANDIDATES = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]

DEFAULT_FONT: str | None = None
for _f in _FONT_CANDIDATES:
    if Path(_f).exists():
        DEFAULT_FONT = _f
        break


def _parse_srt_time(s: str) -> float:
    """Parse SRT timestamp '00:01:23,456' to seconds."""
    s = s.strip().replace(",", ".")
    parts = s.split(":")
    if len(parts) == 3:
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    return 0.0


def _parse_subtitle_file(path: str) -> list[dict]:
    """Parse SRT/VTT file into list of {start, end, text} dicts."""
    content = Path(path).read_text(encoding="utf-8", errors="replace")

    # Strip VTT header if present
    if content.strip().startswith("WEBVTT"):
        content = re.sub(r"^WEBVTT.*?\n\n", "", content.strip(), count=1, flags=re.DOTALL)

    # Split into blocks (SRT and VTT share similar block structure)
    blocks = re.split(r"\n\s*\n", content.strip())
    segments: list[dict] = []

    for block in blocks:
        lines = block.strip().split("\n")
        # Find the timestamp line (contains -->)
        ts_line = None
        ts_idx = -1
        for i, line in enumerate(lines):
            if "-->" in line:
                ts_line = line
                ts_idx = i
                break
        if ts_line is None:
            continue

        match = re.search(
            r"(\d[\d:,.\s]+?)\s*-->\s*(\d[\d:,.\s]+)",
            ts_line,
        )
        if not match:
            continue

        start = _parse_srt_time(match.group(1))
        end = _parse_srt_time(match.group(2))
        text = "\n".join(lines[ts_idx + 1 :]).strip()
        # Strip HTML-like tags (e.g., <i>, <b>)
        text = re.sub(r"<[^>]+>", "", text)
        if text:
            segments.append({"start": start, "end": end, "text": text})

    return segments


def _make_subtitle_overlays(
    subtitle_path: str,
    clip_source_in: float,
    clip_source_out: float,
    clip_size: tuple[int, int],
) -> list[TextClip]:
    """Create TextClip overlays from a subtitle file for the given clip range."""
    try:
        segments = _parse_subtitle_file(subtitle_path)
    except Exception:
        logger.warning("Failed to parse subtitle file: %s", subtitle_path, exc_info=True)
        return []

    clip_duration = clip_source_out - clip_source_in
    overlays: list[TextClip] = []

    for seg in segments:
        # Convert subtitle absolute times to clip-relative times
        rel_start = seg["start"] - clip_source_in
        rel_end = seg["end"] - clip_source_in

        # Skip segments outside clip range
        if rel_end <= 0 or rel_start >= clip_duration:
            continue

        # Clamp to clip boundaries
        rel_start = max(0, rel_start)
        rel_end = min(clip_duration, rel_end)

        if rel_end <= rel_start:
            continue

        try:
            kwargs: dict = {
                "text": seg["text"],
                "font_size": 32,
                "color": "white",
                "stroke_color": "black",
                "stroke_width": 2,
            }
            if DEFAULT_FONT:
                kwargs["font"] = DEFAULT_FONT

            txt = TextClip(**kwargs)
            # Position subtitles at bottom-center
            fw, fh = clip_size
            tw, th = txt.size
            pos = ((fw - tw) // 2, fh - th - 60)
            txt = txt.with_position(pos).with_start(rel_start).with_duration(rel_end - rel_start)
            overlays.append(txt)
        except Exception:
            logger.warning("Failed to create subtitle overlay for: %s", seg["text"][:30], exc_info=True)

    return overlays


def _resolve_position(
    pos_name: str, text_size: tuple[int, int], frame_size: tuple[int, int]
) -> tuple | str:
    """Convert position name to pixel coordinates for MoviePy."""
    if pos_name == "center":
        return "center"

    margin = 40
    tw, th = text_size
    fw, fh = frame_size

    positions = {
        "top": ((fw - tw) // 2, margin),
        "bottom": ((fw - tw) // 2, fh - th - margin),
        "top-left": (margin, margin),
        "top-right": (fw - tw - margin, margin),
        "bottom-left": (margin, fh - th - margin),
        "bottom-right": (fw - tw - margin, fh - th - margin),
    }
    return positions.get(pos_name, "center")


def _make_text_overlay(
    overlay: dict, clip_size: tuple[int, int]
) -> TextClip | None:
    """Create a TextClip from overlay data. Returns None on failure."""
    try:
        text = overlay.get("text", "")
        pos_name = overlay.get("position", "center")
        start = float(overlay.get("start", 0))
        end = float(overlay.get("end", 5))
        style = overlay.get("style", {})
        font_size = int(style.get("font_size", 48))
        color = style.get("color", "white")

        kwargs: dict = {
            "text": text,
            "font_size": font_size,
            "color": color,
            "stroke_color": "black",
            "stroke_width": 2,
        }
        if DEFAULT_FONT:
            kwargs["font"] = DEFAULT_FONT

        txt = TextClip(**kwargs)

        pos = _resolve_position(pos_name, tuple(txt.size), clip_size)
        txt = txt.with_position(pos).with_start(start).with_duration(end - start)
        return txt
    except Exception:
        logger.warning(
            "Failed to create text overlay: %s",
            overlay.get("text", ""),
            exc_info=True,
        )
        return None


def _make_title_card(
    clip: dict, target_size: tuple[int, int]
) -> CompositeVideoClip | None:
    """Create a title card clip (text on solid background). Returns None on failure."""
    try:
        title_data = clip.get("title_card", {})
        text = title_data.get("text", "")
        style = title_data.get("style", {})
        duration = clip["source_out"] - clip["source_in"]

        bg_color = style.get("bg_color", (0, 0, 0))
        if isinstance(bg_color, list):
            bg_color = tuple(bg_color)
        font_size = int(style.get("font_size", 72))
        color = style.get("color", "white")

        bg = ColorClip(size=target_size, color=bg_color).with_duration(duration)

        kwargs: dict = {
            "text": text,
            "font_size": font_size,
            "color": color,
            "stroke_color": "black",
            "stroke_width": 1,
        }
        if DEFAULT_FONT:
            kwargs["font"] = DEFAULT_FONT

        txt = TextClip(**kwargs)
        txt = txt.with_position("center").with_duration(duration)

        return CompositeVideoClip([bg, txt])
    except Exception:
        logger.warning("Failed to create title card", exc_info=True)
        return None


def render_timeline_to_file(
    timeline: dict,
    asset_paths: dict[str, str],
    output_path: Path,
) -> Path:
    """Render timeline clips into a single video file.

    Handles: video subclips, text overlays, title cards, crop,
    and resolution normalization across clips.
    """
    clips = timeline.get("clips", [])
    if not clips:
        raise ValueError("No clips in timeline to render")

    # Determine target resolution from first video clip
    target_size: tuple[int, int] | None = None
    for clip in clips:
        if clip.get("asset_type", "video") != "video":
            continue
        asset_id = clip.get("asset_id")
        fp = asset_paths.get(asset_id, "") if asset_id else ""
        if fp and Path(fp).exists():
            probe = VideoFileClip(fp)
            target_size = (probe.size[0], probe.size[1])
            probe.close()
            break

    if target_size is None:
        target_size = (1920, 1080)

    segments: list = []

    try:
        for clip in clips:
            asset_type = clip.get("asset_type", "video")

            # ── Title cards ──
            if asset_type == "title_card":
                tc = _make_title_card(clip, target_size)
                if tc:
                    segments.append(tc)
                continue

            if asset_type != "video":
                continue

            # ── Video clips ──
            asset_id = clip.get("asset_id")
            file_path = asset_paths.get(asset_id, "") if asset_id else ""
            if not file_path or not Path(file_path).exists():
                logger.warning("Skipping clip %s: asset file not found", clip.get("id"))
                continue

            source_in = clip.get("source_in", 0.0)
            source_out = clip.get("source_out")

            video = VideoFileClip(file_path)

            # Clamp to actual duration
            if source_out is None or source_out > video.duration:
                source_out = video.duration
            if source_in >= source_out:
                video.close()
                continue

            segment = video.subclipped(source_in, source_out)

            # ── Resize to target resolution ──
            seg_size = (segment.size[0], segment.size[1])
            if seg_size != target_size:
                segment = segment.resized(target_size)

            # ── Apply crop ──
            crop_data = clip.get("crop")
            if crop_data:
                try:
                    segment = segment.cropped(
                        x1=crop_data["x"],
                        y1=crop_data["y"],
                        x2=crop_data["x"] + crop_data["width"],
                        y2=crop_data["y"] + crop_data["height"],
                    )
                    # Resize back to target after crop
                    segment = segment.resized(target_size)
                except Exception:
                    logger.warning("Crop failed for clip %s, using uncropped", clip.get("id"), exc_info=True)

            # ── Apply text overlays + subtitles via CompositeVideoClip ──
            layers = [segment]

            # Text overlays
            for ov in clip.get("overlays", []):
                txt = _make_text_overlay(ov, target_size)
                if txt:
                    layers.append(txt)

            # Subtitles (burn-in from SRT/VTT file)
            sub_asset_id = clip.get("subtitle_asset_id")
            if sub_asset_id:
                sub_path = asset_paths.get(sub_asset_id, "")
                if sub_path and Path(sub_path).exists():
                    sub_clips = _make_subtitle_overlays(
                        sub_path, source_in, source_out, target_size
                    )
                    layers.extend(sub_clips)

            if len(layers) > 1:
                segment = CompositeVideoClip(layers)

            segments.append(segment)

        if not segments:
            raise ValueError("No video clips to render")

        if len(segments) == 1:
            final = segments[0]
        else:
            final = concatenate_videoclips(segments, method="compose")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        final.write_videofile(
            str(output_path),
            codec="libx264",
            audio_codec="aac",
            logger=None,
        )
        return output_path
    finally:
        for seg in segments:
            try:
                seg.close()
            except Exception:
                pass
