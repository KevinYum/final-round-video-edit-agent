"""Edit tool definitions for the video edit agent.

Each tool is a descriptor dict with name, description, category, and parameters.
No execution logic — these define what the LLM can plan with.
"""


def _param(name: str, type_: str, required: bool, description: str) -> dict:
    return {"name": name, "type": type_, "required": required, "description": description}


TOOLS: list[dict] = [
    # ── Trim / Cut / Delete ──────────────────────────────────────────
    {
        "name": "trim_clip",
        "description": "Trim a clip by adjusting its source in/out points.",
        "category": "trim",
        "parameters": [
            _param("clip_id", "string", True, "ID of the clip to trim"),
            _param("new_in", "number", True, "New source in point (seconds)"),
            _param("new_out", "number", True, "New source out point (seconds)"),
        ],
    },
    {
        "name": "split_clip",
        "description": "Split a clip into two at a given time offset from the clip's source_in.",
        "category": "trim",
        "parameters": [
            _param("clip_id", "string", True, "ID of the clip to split"),
            _param("split_at", "number", True, "Time offset from source_in to split at (seconds)"),
        ],
    },
    {
        "name": "delete_clip",
        "description": "Remove a clip from the timeline entirely.",
        "category": "trim",
        "parameters": [
            _param("clip_id", "string", True, "ID of the clip to delete"),
        ],
    },
    # ── Reorder / Insert / Replace ───────────────────────────────────
    {
        "name": "reorder_clips",
        "description": "Reorder clips on the timeline by providing the desired clip ID sequence.",
        "category": "reorder",
        "parameters": [
            _param("clip_ids", "array", True, "Ordered list of clip IDs in the desired sequence"),
        ],
    },
    {
        "name": "insert_clip",
        "description": "Insert a new clip from an asset into the timeline at a specific position.",
        "category": "reorder",
        "parameters": [
            _param("asset_id", "string", True, "ID of the source asset"),
            _param("position_after_clip_id", "string", False, "Insert after this clip ID (null = beginning)"),
            _param("source_in", "number", True, "Source in point (seconds)"),
            _param("source_out", "number", True, "Source out point (seconds)"),
        ],
    },
    {
        "name": "replace_clip",
        "description": "Replace a clip with content from a different asset.",
        "category": "reorder",
        "parameters": [
            _param("clip_id", "string", True, "ID of the clip to replace"),
            _param("new_asset_id", "string", True, "ID of the replacement asset"),
            _param("source_in", "number", True, "Source in point of the new asset (seconds)"),
            _param("source_out", "number", True, "Source out point of the new asset (seconds)"),
        ],
    },
    # ── Text Overlays / Titles / Subtitles ───────────────────────────
    {
        "name": "add_text_overlay",
        "description": "Add a text overlay on top of an existing clip.",
        "category": "text",
        "parameters": [
            _param("clip_id", "string", True, "ID of the clip to overlay text on"),
            _param("text", "string", True, "The overlay text content"),
            _param("position", "string", True, "Position: top, center, bottom"),
            _param("start", "number", True, "Start time relative to clip (seconds)"),
            _param("end", "number", True, "End time relative to clip (seconds)"),
            _param("style", "object", False, "Optional style: {font_size, color, background}"),
        ],
    },
    {
        "name": "add_title_card",
        "description": "Insert a title card (text-only clip) into the timeline.",
        "category": "text",
        "parameters": [
            _param("text", "string", True, "Title card text"),
            _param("duration", "number", True, "Duration of the title card (seconds)"),
            _param("position_before_clip_id", "string", False, "Insert before this clip ID (null = end)"),
            _param("style", "object", False, "Optional style: {font_size, color, background_color}"),
        ],
    },
    {
        "name": "add_subtitles",
        "description": "Attach a subtitle asset to a clip for rendering.",
        "category": "text",
        "parameters": [
            _param("clip_id", "string", True, "ID of the clip to add subtitles to"),
            _param("subtitle_asset_id", "string", True, "ID of the subtitle asset file"),
        ],
    },
    # ── Aspect Ratio / Crop / Reframe ────────────────────────────────
    {
        "name": "change_aspect_ratio",
        "description": "Change the project's target aspect ratio (e.g., 16:9, 9:16, 1:1).",
        "category": "aspect",
        "parameters": [
            _param("new_ratio", "string", True, "Target aspect ratio (e.g., '16:9', '9:16', '1:1')"),
        ],
    },
    {
        "name": "crop_clip",
        "description": "Crop a clip to a specific region.",
        "category": "aspect",
        "parameters": [
            _param("clip_id", "string", True, "ID of the clip to crop"),
            _param("x", "number", True, "Crop region top-left X (pixels)"),
            _param("y", "number", True, "Crop region top-left Y (pixels)"),
            _param("width", "number", True, "Crop region width (pixels)"),
            _param("height", "number", True, "Crop region height (pixels)"),
        ],
    },
]


def get_all_tools() -> list[dict]:
    """Return all tool definitions."""
    return TOOLS


def _tools_by_name() -> dict[str, dict]:
    """Build a lookup of tool name → tool definition."""
    return {t["name"]: t for t in TOOLS}


def validate_plan(plan: dict) -> list[str]:
    """Validate an edit plan against tool definitions.

    Returns a list of error strings. Empty list means the plan is valid.
    Checks:
      - Each step has a valid tool_name
      - All required params are present
      - No unknown params are passed
    """
    errors: list[str] = []
    lookup = _tools_by_name()
    steps = plan.get("steps", [])

    if not steps:
        errors.append("Edit plan has no steps.")
        return errors

    for step in steps:
        num = step.get("step_number", "?")
        tool_name = step.get("tool_name", "")
        params = step.get("params", {})

        # Check tool exists
        if tool_name not in lookup:
            errors.append(f"Step {num}: unknown tool '{tool_name}'.")
            continue

        tool_def = lookup[tool_name]
        defined_params = {p["name"]: p for p in tool_def["parameters"]}

        # Check required params are present
        for pname, pdef in defined_params.items():
            if pdef["required"] and pname not in params:
                errors.append(
                    f"Step {num} ({tool_name}): missing required param '{pname}'."
                )

        # Check for unknown params
        for pname in params:
            if pname not in defined_params:
                errors.append(
                    f"Step {num} ({tool_name}): unknown param '{pname}'."
                )

    return errors


def get_tools_prompt() -> str:
    """Format tool definitions as a string for the LLM system prompt."""
    lines = ["Available editing tools:\n"]
    for tool in TOOLS:
        lines.append(f"### {tool['name']}")
        lines.append(f"{tool['description']}")
        lines.append("Parameters:")
        for p in tool["parameters"]:
            req = "required" if p["required"] else "optional"
            lines.append(f"  - {p['name']} ({p['type']}, {req}): {p['description']}")
        lines.append("")
    return "\n".join(lines)
