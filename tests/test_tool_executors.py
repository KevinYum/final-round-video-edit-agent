"""Tests for tool executor functions."""

import copy

import pytest

from backend.services.tool_executors import (
    ToolContext,
    ToolExecutionError,
    add_subtitles,
    add_text_overlay,
    add_title_card,
    change_aspect_ratio,
    crop_clip,
    delete_clip,
    insert_clip,
    recompute_timeline,
    reorder_clips,
    replace_clip,
    split_clip,
    trim_clip,
)


# ── Fixtures ────────────────────────────────────────────────────────

SAMPLE_TIMELINE = {
    "version": "0.3.0",
    "total_duration": 20.0,
    "clips": [
        {
            "id": "clip-aaa",
            "asset_id": "asset-1",
            "asset_name": "video1.mp4",
            "asset_type": "video",
            "source_in": 0.0,
            "source_out": 10.0,
            "timeline_start": 0.0,
            "width": 1920,
            "height": 1080,
            "format": "mp4",
            "transcript": None,
        },
        {
            "id": "clip-bbb",
            "asset_id": "asset-2",
            "asset_name": "video2.mp4",
            "asset_type": "video",
            "source_in": 0.0,
            "source_out": 10.0,
            "timeline_start": 10.0,
            "width": 1280,
            "height": 720,
            "format": "mp4",
            "transcript": None,
        },
    ],
}

SAMPLE_ASSETS = [
    {"id": "asset-1", "asset_type": "video", "original_filename": "video1.mp4", "duration_seconds": 30.0, "width": 1920, "height": 1080, "format": "mp4"},
    {"id": "asset-2", "asset_type": "video", "original_filename": "video2.mp4", "duration_seconds": 25.0, "width": 1280, "height": 720, "format": "mp4"},
    {"id": "asset-sub", "asset_type": "subtitle", "original_filename": "subs.srt", "duration_seconds": None, "width": None, "height": None, "format": "srt"},
]

CTX = ToolContext(project_id="test-project", project_assets=SAMPLE_ASSETS)


def fresh_timeline():
    return copy.deepcopy(SAMPLE_TIMELINE)


# ── recompute_timeline ──────────────────────────────────────────────


def test_recompute_timeline():
    tl = fresh_timeline()
    # Mess up timeline_start values
    tl["clips"][0]["timeline_start"] = 999.0
    tl["clips"][1]["timeline_start"] = 999.0
    recompute_timeline(tl)
    assert tl["clips"][0]["timeline_start"] == 0.0
    assert tl["clips"][1]["timeline_start"] == 10.0
    assert tl["total_duration"] == 20.0


def test_recompute_timeline_after_trim():
    tl = fresh_timeline()
    tl["clips"][0]["source_out"] = 5.0  # trim first clip to 5s
    recompute_timeline(tl)
    assert tl["clips"][1]["timeline_start"] == 5.0
    assert tl["total_duration"] == 15.0


# ── trim_clip ───────────────────────────────────────────────────────


def test_trim_clip():
    tl = fresh_timeline()
    trim_clip(tl, {"clip_id": "clip-aaa", "new_in": 2.0, "new_out": 7.0}, CTX)
    clip = tl["clips"][0]
    assert clip["source_in"] == 2.0
    assert clip["source_out"] == 7.0


def test_trim_clip_invalid_range():
    tl = fresh_timeline()
    with pytest.raises(ToolExecutionError, match="new_out.*must be > new_in"):
        trim_clip(tl, {"clip_id": "clip-aaa", "new_in": 5.0, "new_out": 3.0}, CTX)


def test_trim_clip_not_found():
    tl = fresh_timeline()
    with pytest.raises(ToolExecutionError, match="Clip not found"):
        trim_clip(tl, {"clip_id": "nonexistent", "new_in": 0, "new_out": 5}, CTX)


# ── split_clip ──────────────────────────────────────────────────────


def test_split_clip():
    tl = fresh_timeline()
    split_clip(tl, {"clip_id": "clip-aaa", "split_at": 4.0}, CTX)
    assert len(tl["clips"]) == 3
    assert tl["clips"][0]["id"] == "clip-aaa"
    assert tl["clips"][0]["source_out"] == 4.0
    assert tl["clips"][1]["source_in"] == 4.0
    assert tl["clips"][1]["source_out"] == 10.0
    assert tl["clips"][1]["id"] != "clip-aaa"  # new ID


def test_split_clip_out_of_range():
    tl = fresh_timeline()
    with pytest.raises(ToolExecutionError, match="split_at.*must be between"):
        split_clip(tl, {"clip_id": "clip-aaa", "split_at": 10.0}, CTX)


def test_split_clip_zero():
    tl = fresh_timeline()
    with pytest.raises(ToolExecutionError, match="split_at.*must be between"):
        split_clip(tl, {"clip_id": "clip-aaa", "split_at": 0.0}, CTX)


# ── delete_clip ─────────────────────────────────────────────────────


def test_delete_clip():
    tl = fresh_timeline()
    delete_clip(tl, {"clip_id": "clip-aaa"}, CTX)
    assert len(tl["clips"]) == 1
    assert tl["clips"][0]["id"] == "clip-bbb"


def test_delete_clip_not_found():
    tl = fresh_timeline()
    with pytest.raises(ToolExecutionError, match="Clip not found"):
        delete_clip(tl, {"clip_id": "nonexistent"}, CTX)


# ── reorder_clips ───────────────────────────────────────────────────


def test_reorder_clips():
    tl = fresh_timeline()
    reorder_clips(tl, {"clip_ids": ["clip-bbb", "clip-aaa"]}, CTX)
    assert tl["clips"][0]["id"] == "clip-bbb"
    assert tl["clips"][1]["id"] == "clip-aaa"


def test_reorder_clips_mismatch():
    tl = fresh_timeline()
    with pytest.raises(ToolExecutionError, match="clip_ids mismatch"):
        reorder_clips(tl, {"clip_ids": ["clip-aaa"]}, CTX)


# ── insert_clip ─────────────────────────────────────────────────────


def test_insert_clip_at_beginning():
    tl = fresh_timeline()
    insert_clip(tl, {"asset_id": "asset-1", "source_in": 0.0, "source_out": 3.0}, CTX)
    assert len(tl["clips"]) == 3
    assert tl["clips"][0]["asset_id"] == "asset-1"
    assert tl["clips"][0]["source_out"] == 3.0


def test_insert_clip_after():
    tl = fresh_timeline()
    insert_clip(tl, {"asset_id": "asset-2", "position_after_clip_id": "clip-aaa", "source_in": 5.0, "source_out": 10.0}, CTX)
    assert len(tl["clips"]) == 3
    assert tl["clips"][1]["asset_id"] == "asset-2"
    assert tl["clips"][1]["source_in"] == 5.0


def test_insert_clip_asset_not_found():
    tl = fresh_timeline()
    with pytest.raises(ToolExecutionError, match="Asset not found"):
        insert_clip(tl, {"asset_id": "nonexistent", "source_in": 0, "source_out": 5}, CTX)


# ── replace_clip ────────────────────────────────────────────────────


def test_replace_clip():
    tl = fresh_timeline()
    replace_clip(tl, {"clip_id": "clip-aaa", "new_asset_id": "asset-2", "source_in": 2.0, "source_out": 8.0}, CTX)
    clip = tl["clips"][0]
    assert clip["asset_id"] == "asset-2"
    assert clip["source_in"] == 2.0
    assert clip["source_out"] == 8.0
    assert clip["width"] == 1280


def test_replace_clip_asset_not_found():
    tl = fresh_timeline()
    with pytest.raises(ToolExecutionError, match="Asset not found"):
        replace_clip(tl, {"clip_id": "clip-aaa", "new_asset_id": "nope", "source_in": 0, "source_out": 5}, CTX)


# ── add_text_overlay ────────────────────────────────────────────────


def test_add_text_overlay():
    tl = fresh_timeline()
    add_text_overlay(tl, {"clip_id": "clip-aaa", "text": "Hello", "position": "bottom", "start": 0.0, "end": 3.0}, CTX)
    assert len(tl["clips"][0]["overlays"]) == 1
    assert tl["clips"][0]["overlays"][0]["text"] == "Hello"


def test_add_text_overlay_invalid_range():
    tl = fresh_timeline()
    with pytest.raises(ToolExecutionError, match="invalid for clip duration"):
        add_text_overlay(tl, {"clip_id": "clip-aaa", "text": "Hi", "position": "top", "start": 0.0, "end": 15.0}, CTX)


# ── add_title_card ──────────────────────────────────────────────────


def test_add_title_card_at_end():
    tl = fresh_timeline()
    add_title_card(tl, {"text": "The End", "duration": 3.0}, CTX)
    assert len(tl["clips"]) == 3
    assert tl["clips"][-1]["asset_type"] == "title_card"
    assert tl["clips"][-1]["title_card"]["text"] == "The End"
    assert tl["clips"][-1]["source_out"] == 3.0


def test_add_title_card_before_clip():
    tl = fresh_timeline()
    add_title_card(tl, {"text": "Intro", "duration": 2.0, "position_before_clip_id": "clip-aaa"}, CTX)
    assert len(tl["clips"]) == 3
    assert tl["clips"][0]["asset_type"] == "title_card"
    assert tl["clips"][1]["id"] == "clip-aaa"


def test_add_title_card_zero_duration():
    tl = fresh_timeline()
    with pytest.raises(ToolExecutionError, match="duration must be > 0"):
        add_title_card(tl, {"text": "Bad", "duration": 0.0}, CTX)


# ── add_subtitles ───────────────────────────────────────────────────


def test_add_subtitles():
    tl = fresh_timeline()
    add_subtitles(tl, {"clip_id": "clip-aaa", "subtitle_asset_id": "asset-sub"}, CTX)
    assert tl["clips"][0]["subtitle_asset_id"] == "asset-sub"


def test_add_subtitles_asset_not_found():
    tl = fresh_timeline()
    with pytest.raises(ToolExecutionError, match="Asset not found"):
        add_subtitles(tl, {"clip_id": "clip-aaa", "subtitle_asset_id": "nope"}, CTX)


# ── change_aspect_ratio ─────────────────────────────────────────────


def test_change_aspect_ratio():
    tl = fresh_timeline()
    change_aspect_ratio(tl, {"new_ratio": "9:16"}, CTX)
    assert tl["_pending_aspect_ratio"] == "9:16"


def test_change_aspect_ratio_invalid():
    tl = fresh_timeline()
    with pytest.raises(ToolExecutionError, match="Invalid aspect ratio"):
        change_aspect_ratio(tl, {"new_ratio": "5:3"}, CTX)


# ── crop_clip ───────────────────────────────────────────────────────


def test_crop_clip():
    tl = fresh_timeline()
    crop_clip(tl, {"clip_id": "clip-aaa", "x": 100, "y": 50, "width": 800, "height": 600}, CTX)
    assert tl["clips"][0]["crop"] == {"x": 100, "y": 50, "width": 800, "height": 600}


def test_crop_clip_exceeds_dimensions():
    tl = fresh_timeline()
    with pytest.raises(ToolExecutionError, match="exceeds clip dimensions"):
        crop_clip(tl, {"clip_id": "clip-aaa", "x": 1800, "y": 0, "width": 200, "height": 100}, CTX)


def test_crop_clip_negative_origin():
    tl = fresh_timeline()
    with pytest.raises(ToolExecutionError, match="non-negative"):
        crop_clip(tl, {"clip_id": "clip-aaa", "x": -1, "y": 0, "width": 100, "height": 100}, CTX)
