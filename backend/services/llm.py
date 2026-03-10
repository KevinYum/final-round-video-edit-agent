"""LLM service — calls OpenAI via LangChain to produce edit plans."""

import json
import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from backend.config import OPENAI_API_KEY, OPENAI_MODEL
from backend.services.tools import get_tools_prompt

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """You are a video editing assistant. You help users edit their video projects by analyzing their requests and producing strictly executable edit plans.

## Project Context
**Project ID**: {project_id}
**Target Aspect Ratio**: {aspect_ratio}
**Language**: {language}

### Current Timeline
```json
{timeline_json}
```

### Available Assets
{assets_text}

### {tools_prompt}

### Current Edit Plan
{current_plan_text}

## Your Task
Analyze the user's new editing request and respond with a JSON object. You must iterate on the **Current Edit Plan** above — incorporate the user's new request by adding, removing, or modifying steps as needed, and return the full updated plan.

```json
{{
  "assistant_message": "A natural language explanation of what you changed in the plan",
  "edit_plan": {{
    "steps": [
      {{
        "step_number": 1,
        "tool_name": "tool_name_here",
        "params": {{
          "param_name": "exact_value"
        }}
      }}
    ],
    "summary": "Brief summary of the overall edit"
  }},
  "needs_clarification": false
}}
```

### Rules
- Always start from the **Current Edit Plan** and iterate on it. Add new steps for the user's latest request, modify existing steps if the user wants changes, or remove steps if the user asks to undo something. The returned `edit_plan` must be the complete updated plan, not just the new steps.
- If the current edit plan is empty, create a new plan from scratch based on the user's request.
- Each step's `tool_name` must be one of the available tools listed above.
- Each step's `params` must contain ALL required parameters for that tool, using the EXACT parameter names defined above.
- Parameter values must be concrete: use actual clip IDs, asset IDs, and numeric values from the timeline/assets. Never use placeholders.
- `params` must be directly executable — they will be passed as keyword arguments to tool functions (e.g., `trim_clip(**params)`).
- If you cannot determine the exact parameter values from the user's request and timeline context, set `needs_clarification` to `true`, set `edit_plan` to `null`, and ask clarifying questions in `assistant_message`.
- Respond ONLY with the JSON object, no markdown fences or extra text.
"""


def _build_system_prompt(
    project_id: str,
    aspect_ratio: str | None,
    language: str | None,
    timeline: dict | None,
    assets: list[dict],
    current_plan: dict | None = None,
) -> str:
    assets_lines = []
    for a in assets:
        dur = f", {a['duration_seconds']}s" if a.get("duration_seconds") else ""
        res = ""
        if a.get("width") and a.get("height"):
            res = f", {a['width']}x{a['height']}"
        assets_lines.append(f"- {a['id']}: {a['original_filename']} ({a['asset_type']}{dur}{res})")
    assets_text = "\n".join(assets_lines) if assets_lines else "(no assets uploaded)"

    if current_plan and current_plan.get("steps"):
        current_plan_text = "```json\n" + json.dumps(current_plan, indent=2) + "\n```"
    else:
        current_plan_text = "(no plan yet — create a new plan from the user's request)"

    return SYSTEM_PROMPT_TEMPLATE.format(
        project_id=project_id,
        aspect_ratio=aspect_ratio or "not set",
        language=language or "not set",
        timeline_json=json.dumps(timeline, indent=2) if timeline else "{}",
        assets_text=assets_text,
        tools_prompt=get_tools_prompt(),
        current_plan_text=current_plan_text,
    )


def _build_messages(
    system_prompt: str,
    conversation_history: list[dict],
    new_message: str,
) -> list:
    messages = [SystemMessage(content=system_prompt)]
    for msg in conversation_history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            # Reconstruct the full JSON the LLM originally returned so it
            # can see its own prior plans and iterate on them.
            response_obj = {
                "assistant_message": msg["content"],
                "edit_plan": msg.get("edit_plan"),
                "needs_clarification": msg.get("needs_clarification", False),
            }
            messages.append(AIMessage(content=json.dumps(response_obj)))
    messages.append(HumanMessage(content=new_message))
    return messages


def _parse_llm_response(raw: str) -> dict:
    """Parse LLM response JSON. Returns a fallback on failure."""
    # Strip markdown fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]  # remove opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM JSON response, returning clarification fallback")
        return {
            "assistant_message": raw,
            "edit_plan": None,
            "needs_clarification": True,
        }


async def call_llm(
    project_id: str,
    aspect_ratio: str | None,
    language: str | None,
    timeline: dict | None,
    assets: list[dict],
    conversation_history: list[dict],
    new_message: str,
    current_plan: dict | None = None,
) -> dict:
    """Call the LLM and return parsed response dict.

    Returns: {"assistant_message": str, "edit_plan": dict|None, "needs_clarification": bool}
    """
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not configured")

    system_prompt = _build_system_prompt(
        project_id, aspect_ratio, language, timeline, assets, current_plan
    )
    messages = _build_messages(system_prompt, conversation_history, new_message)

    llm = ChatOpenAI(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY,
        temperature=0,
    )

    response: AIMessage = await llm.ainvoke(messages)
    return _parse_llm_response(response.content)
