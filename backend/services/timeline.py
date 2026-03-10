import uuid


TIMELINE_VERSION = "0.3.0"
DEFAULT_IMAGE_DURATION = 5.0


def create_empty_timeline() -> dict:
    """An empty timeline — the output is a sequence of clips."""
    return {
        "version": TIMELINE_VERSION,
        "total_duration": 0.0,
        "clips": [],
    }



def add_assets_to_timeline(
    timeline: dict,
    assets: list[dict],
) -> dict:
    """Append assets to the timeline as clips in output order.

    Each asset dict must have: id, asset_type, original_filename, duration_seconds (nullable).
    The timeline is the final output sequence: an ordered list of clips
    where each clip says "play asset X from source_in to source_out".
    """
    NON_CLIP_TYPES = {"subtitle"}

    clips = timeline.get("clips", [])

    # Current end of the output timeline
    output_cursor = 0.0
    if clips:
        last = clips[-1]
        output_cursor = last["timeline_start"] + (last["source_out"] - last["source_in"])

    for asset in assets:
        if asset["asset_type"] in NON_CLIP_TYPES:
            continue

        duration = asset.get("duration_seconds") or DEFAULT_IMAGE_DURATION
        clip = {
            "id": f"clip-{uuid.uuid4().hex[:8]}",
            "asset_id": asset["id"],
            "asset_name": asset.get("original_filename", ""),
            "asset_type": asset["asset_type"],
            "source_in": 0.0,
            "source_out": duration,
            "timeline_start": output_cursor,
            "width": asset.get("width"),
            "height": asset.get("height"),
            "format": asset.get("format"),
            "transcript": None,
        }
        clips.append(clip)
        output_cursor += duration

    timeline["clips"] = clips
    timeline["total_duration"] = output_cursor
    return timeline
