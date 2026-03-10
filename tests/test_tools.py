from backend.services.tools import get_all_tools, get_tools_prompt, validate_plan


def test_get_all_tools_returns_11():
    tools = get_all_tools()
    assert len(tools) == 11


def test_tool_structure():
    for tool in get_all_tools():
        assert "name" in tool
        assert "description" in tool
        assert "category" in tool
        assert "parameters" in tool
        assert isinstance(tool["parameters"], list)
        for param in tool["parameters"]:
            assert "name" in param
            assert "type" in param
            assert "required" in param
            assert "description" in param


def test_tool_names():
    names = {t["name"] for t in get_all_tools()}
    expected = {
        "trim_clip", "split_clip", "delete_clip",
        "reorder_clips", "insert_clip", "replace_clip",
        "add_text_overlay", "add_title_card", "add_subtitles",
        "change_aspect_ratio", "crop_clip",
    }
    assert names == expected


def test_tool_categories():
    categories = {t["category"] for t in get_all_tools()}
    assert categories == {"trim", "reorder", "text", "aspect"}


def test_get_tools_prompt():
    prompt = get_tools_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 100
    assert "trim_clip" in prompt
    assert "change_aspect_ratio" in prompt


# ── Plan Validation Tests ─────────────────────────────────────────────


def test_validate_plan_valid():
    plan = {
        "steps": [
            {"step_number": 1, "tool_name": "trim_clip", "params": {"clip_id": "c1", "new_in": 0, "new_out": 5}},
        ],
        "summary": "Trim clip",
    }
    errors = validate_plan(plan)
    assert errors == []


def test_validate_plan_valid_multi_step():
    plan = {
        "steps": [
            {"step_number": 1, "tool_name": "trim_clip", "params": {"clip_id": "c1", "new_in": 0, "new_out": 5}},
            {"step_number": 2, "tool_name": "delete_clip", "params": {"clip_id": "c2"}},
        ],
        "summary": "Trim and delete",
    }
    errors = validate_plan(plan)
    assert errors == []


def test_validate_plan_unknown_tool():
    plan = {
        "steps": [
            {"step_number": 1, "tool_name": "nonexistent_tool", "params": {"x": 1}},
        ],
        "summary": "Bad plan",
    }
    errors = validate_plan(plan)
    assert len(errors) == 1
    assert "unknown tool" in errors[0]


def test_validate_plan_missing_required_param():
    plan = {
        "steps": [
            {"step_number": 1, "tool_name": "trim_clip", "params": {"clip_id": "c1"}},
        ],
        "summary": "Missing params",
    }
    errors = validate_plan(plan)
    assert len(errors) == 2  # missing new_in and new_out
    assert all("missing required param" in e for e in errors)


def test_validate_plan_unknown_param():
    plan = {
        "steps": [
            {"step_number": 1, "tool_name": "delete_clip", "params": {"clip_id": "c1", "bogus": True}},
        ],
        "summary": "Extra param",
    }
    errors = validate_plan(plan)
    assert len(errors) == 1
    assert "unknown param" in errors[0]


def test_validate_plan_empty_steps():
    plan = {"steps": [], "summary": "Empty"}
    errors = validate_plan(plan)
    assert len(errors) == 1
    assert "no steps" in errors[0].lower()


def test_validate_plan_optional_params_ok():
    """Optional params should not cause errors when omitted."""
    plan = {
        "steps": [
            {
                "step_number": 1,
                "tool_name": "add_text_overlay",
                "params": {
                    "clip_id": "c1", "text": "Hello", "position": "center",
                    "start": 0, "end": 3,
                    # "style" is optional — omitted intentionally
                },
            },
        ],
        "summary": "Text overlay without style",
    }
    errors = validate_plan(plan)
    assert errors == []
