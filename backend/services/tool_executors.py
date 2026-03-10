"""Tool executor functions — each mutates a timeline dict in place.

Every executor has the signature:
    def tool_name(timeline: dict, params: dict, context: ToolContext) -> None

Raises ToolExecutionError on failure.
"""

import copy
import uuid
from dataclasses import dataclass


class ToolExecutionError(Exception):
    """Raised when a tool execution step fails."""


@dataclass
class ToolContext:
    """Contextual data available to tool executors."""

    project_id: str
    project_assets: list[dict]


# ── Helpers ─────────────────────────────────────────────────────────


def _find_clip(timeline: dict, clip_id: str) -> dict:
    for clip in timeline.get("clips", []):
        if clip["id"] == clip_id:
            return clip
    raise ToolExecutionError(f"Clip not found: {clip_id}")


def _find_clip_index(timeline: dict, clip_id: str) -> int:
    for i, clip in enumerate(timeline.get("clips", [])):
        if clip["id"] == clip_id:
            return i
    raise ToolExecutionError(f"Clip not found: {clip_id}")


def _find_asset(context: ToolContext, asset_id: str) -> dict:
    for asset in context.project_assets:
        if asset["id"] == asset_id:
            return asset
    raise ToolExecutionError(f"Asset not found: {asset_id}")


def recompute_timeline(timeline: dict) -> None:
    """Recompute timeline_start for all clips and total_duration."""
    cursor = 0.0
    for clip in timeline.get("clips", []):
        clip["timeline_start"] = cursor
        cursor += clip["source_out"] - clip["source_in"]
    timeline["total_duration"] = cursor


# ── Tool Executors ──────────────────────────────────────────────────


def trim_clip(timeline: dict, params: dict, context: ToolContext) -> None:
    clip = _find_clip(timeline, params["clip_id"])
    new_in = float(params["new_in"])
    new_out = float(params["new_out"])
    if new_in < 0:
        raise ToolExecutionError(f"new_in must be >= 0, got {new_in}")
    if new_out <= new_in:
        raise ToolExecutionError(f"new_out ({new_out}) must be > new_in ({new_in})")
    clip["source_in"] = new_in
    clip["source_out"] = new_out


def split_clip(timeline: dict, params: dict, context: ToolContext) -> None:
    clip_id = params["clip_id"]
    split_at = float(params["split_at"])
    idx = _find_clip_index(timeline, clip_id)
    clip = timeline["clips"][idx]

    clip_duration = clip["source_out"] - clip["source_in"]
    if split_at <= 0 or split_at >= clip_duration:
        raise ToolExecutionError(
            f"split_at ({split_at}) must be between 0 and clip duration ({clip_duration})"
        )

    split_point = clip["source_in"] + split_at

    clip1 = copy.deepcopy(clip)
    clip1["source_out"] = split_point

    clip2 = copy.deepcopy(clip)
    clip2["id"] = f"clip-{uuid.uuid4().hex[:8]}"
    clip2["source_in"] = split_point

    timeline["clips"][idx : idx + 1] = [clip1, clip2]


def delete_clip(timeline: dict, params: dict, context: ToolContext) -> None:
    idx = _find_clip_index(timeline, params["clip_id"])
    timeline["clips"].pop(idx)


def reorder_clips(timeline: dict, params: dict, context: ToolContext) -> None:
    clip_ids = params["clip_ids"]
    clips_by_id = {c["id"]: c for c in timeline.get("clips", [])}
    existing_ids = set(clips_by_id.keys())
    requested_ids = set(clip_ids)

    if requested_ids != existing_ids:
        missing = existing_ids - requested_ids
        extra = requested_ids - existing_ids
        parts = []
        if missing:
            parts.append(f"missing: {missing}")
        if extra:
            parts.append(f"unknown: {extra}")
        raise ToolExecutionError(f"clip_ids mismatch: {'; '.join(parts)}")

    timeline["clips"] = [clips_by_id[cid] for cid in clip_ids]


def insert_clip(timeline: dict, params: dict, context: ToolContext) -> None:
    asset = _find_asset(context, params["asset_id"])
    source_in = float(params["source_in"])
    source_out = float(params["source_out"])
    position_after = params.get("position_after_clip_id")

    if source_out <= source_in:
        raise ToolExecutionError(f"source_out ({source_out}) must be > source_in ({source_in})")

    new_clip = {
        "id": f"clip-{uuid.uuid4().hex[:8]}",
        "asset_id": params["asset_id"],
        "asset_name": asset.get("original_filename", ""),
        "asset_type": asset.get("asset_type", "video"),
        "source_in": source_in,
        "source_out": source_out,
        "timeline_start": 0.0,
        "width": asset.get("width"),
        "height": asset.get("height"),
        "format": asset.get("format"),
        "transcript": None,
    }

    clips = timeline.get("clips", [])
    if position_after is None:
        clips.insert(0, new_clip)
    else:
        idx = _find_clip_index(timeline, position_after)
        clips.insert(idx + 1, new_clip)
    timeline["clips"] = clips


def replace_clip(timeline: dict, params: dict, context: ToolContext) -> None:
    clip = _find_clip(timeline, params["clip_id"])
    asset = _find_asset(context, params["new_asset_id"])
    source_in = float(params["source_in"])
    source_out = float(params["source_out"])

    if source_out <= source_in:
        raise ToolExecutionError(f"source_out ({source_out}) must be > source_in ({source_in})")

    clip["asset_id"] = params["new_asset_id"]
    clip["asset_name"] = asset.get("original_filename", "")
    clip["asset_type"] = asset.get("asset_type", "video")
    clip["source_in"] = source_in
    clip["source_out"] = source_out
    clip["width"] = asset.get("width")
    clip["height"] = asset.get("height")
    clip["format"] = asset.get("format")
    clip.pop("overlays", None)
    clip.pop("subtitle_asset_id", None)
    clip.pop("crop", None)


def add_text_overlay(timeline: dict, params: dict, context: ToolContext) -> None:
    clip = _find_clip(timeline, params["clip_id"])
    clip_duration = clip["source_out"] - clip["source_in"]
    start = float(params["start"])
    end = float(params["end"])

    if start < 0 or end > clip_duration or start >= end:
        raise ToolExecutionError(
            f"Overlay time range [{start}, {end}] invalid for clip duration {clip_duration}"
        )

    overlay = {
        "id": f"overlay-{uuid.uuid4().hex[:8]}",
        "text": params["text"],
        "position": params["position"],
        "start": start,
        "end": end,
        "style": params.get("style", {}),
    }

    if "overlays" not in clip:
        clip["overlays"] = []
    clip["overlays"].append(overlay)


def add_title_card(timeline: dict, params: dict, context: ToolContext) -> None:
    duration = float(params["duration"])
    position_before = params.get("position_before_clip_id")

    if duration <= 0:
        raise ToolExecutionError(f"Title card duration must be > 0, got {duration}")

    title_clip = {
        "id": f"clip-{uuid.uuid4().hex[:8]}",
        "asset_id": None,
        "asset_name": None,
        "asset_type": "title_card",
        "source_in": 0.0,
        "source_out": duration,
        "timeline_start": 0.0,
        "width": None,
        "height": None,
        "format": None,
        "transcript": None,
        "title_card": {
            "text": params["text"],
            "style": params.get("style", {}),
        },
    }

    clips = timeline.get("clips", [])
    if position_before is None:
        clips.append(title_clip)
    else:
        idx = _find_clip_index(timeline, position_before)
        clips.insert(idx, title_clip)
    timeline["clips"] = clips


def add_subtitles(timeline: dict, params: dict, context: ToolContext) -> None:
    clip = _find_clip(timeline, params["clip_id"])
    _find_asset(context, params["subtitle_asset_id"])
    clip["subtitle_asset_id"] = params["subtitle_asset_id"]


def change_aspect_ratio(timeline: dict, params: dict, context: ToolContext) -> None:
    new_ratio = params["new_ratio"]
    valid = {"16:9", "9:16", "1:1", "4:3", "4:5", "21:9"}
    if new_ratio not in valid:
        raise ToolExecutionError(f"Invalid aspect ratio '{new_ratio}'. Valid: {valid}")
    timeline["_pending_aspect_ratio"] = new_ratio


def crop_clip(timeline: dict, params: dict, context: ToolContext) -> None:
    clip = _find_clip(timeline, params["clip_id"])
    x = int(params["x"])
    y = int(params["y"])
    width = int(params["width"])
    height = int(params["height"])

    if width <= 0 or height <= 0:
        raise ToolExecutionError(f"Crop dimensions must be positive: {width}x{height}")
    if x < 0 or y < 0:
        raise ToolExecutionError(f"Crop origin must be non-negative: ({x}, {y})")

    if clip.get("width") and clip.get("height"):
        if x + width > clip["width"] or y + height > clip["height"]:
            raise ToolExecutionError(
                f"Crop region ({x},{y},{width},{height}) exceeds clip "
                f"dimensions ({clip['width']}x{clip['height']})"
            )

    clip["crop"] = {"x": x, "y": y, "width": width, "height": height}


# ── Registry ────────────────────────────────────────────────────────

TOOL_REGISTRY: dict[str, callable] = {
    "trim_clip": trim_clip,
    "split_clip": split_clip,
    "delete_clip": delete_clip,
    "reorder_clips": reorder_clips,
    "insert_clip": insert_clip,
    "replace_clip": replace_clip,
    "add_text_overlay": add_text_overlay,
    "add_title_card": add_title_card,
    "add_subtitles": add_subtitles,
    "change_aspect_ratio": change_aspect_ratio,
    "crop_clip": crop_clip,
}
