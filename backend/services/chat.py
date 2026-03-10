"""Chat orchestrator — handles the chat endpoint logic."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from backend.models.project import Project
from backend.schemas.chat import ChatResponse, EditPlan, ToolStep
from backend.services import llm as llm_service
from backend.services import version as version_service
from backend.services.tools import validate_plan


async def handle_chat(
    project_id: str,
    message: str,
    db: AsyncSession,
) -> ChatResponse:
    """Process a chat message and return a structured response (planning only)."""
    # 1. Load project with assets
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id)
        .options(selectinload(Project.assets))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise ValueError(f"Project not found: {project_id}")

    # 2. Get or create current version
    current_version = await version_service.ensure_version(
        project_id, project.timeline, db
    )

    # 3. Load conversation history for current version
    history = await version_service.get_conversation_history(current_version, db)

    # 3b. Extract the latest valid edit plan from history
    current_plan = None
    for msg in reversed(history):
        if msg["role"] == "assistant" and msg.get("edit_plan") and not msg.get("needs_clarification"):
            current_plan = msg["edit_plan"]
            break

    # 4. Build asset info for LLM
    assets_info = [
        {
            "id": a.id,
            "original_filename": a.original_filename,
            "asset_type": a.asset_type,
            "duration_seconds": a.duration_seconds,
            "width": a.width,
            "height": a.height,
        }
        for a in project.assets
    ]

    # 5. Call LLM with current plan as explicit context
    llm_result = await llm_service.call_llm(
        project_id=project_id,
        aspect_ratio=project.target_aspect_ratio,
        language=project.language,
        timeline=project.timeline,
        assets=assets_info,
        conversation_history=history,
        new_message=message,
        current_plan=current_plan,
    )

    # 6. Parse edit plan
    edit_plan = None
    raw_plan = llm_result.get("edit_plan")
    if raw_plan and isinstance(raw_plan, dict):
        steps = [
            ToolStep(
                step_number=s.get("step_number", i + 1),
                tool_name=s.get("tool_name", ""),
                params=s.get("params", {}),
            )
            for i, s in enumerate(raw_plan.get("steps", []))
        ]
        edit_plan = EditPlan(
            steps=steps,
            summary=raw_plan.get("summary", ""),
        )

    needs_clarification = llm_result.get("needs_clarification", False)
    assistant_message = llm_result.get("assistant_message", "")

    # 6b. Validate the plan against tool definitions
    if edit_plan and not needs_clarification:
        validation_errors = validate_plan(raw_plan)
        if validation_errors:
            error_details = "; ".join(validation_errors)
            assistant_message += (
                f"\n\n[Plan validation failed: {error_details}. "
                "Please provide more details so I can create a valid plan.]"
            )
            edit_plan = None
            needs_clarification = True

    # 7. Store conversation messages
    edit_plan_dict = edit_plan.model_dump() if edit_plan else None

    await version_service.add_message(
        current_version, "user", message, None, False, db
    )
    await version_service.add_message(
        current_version, "assistant", assistant_message,
        edit_plan_dict, needs_clarification, db
    )

    await db.commit()

    return ChatResponse(
        assistant_message=assistant_message,
        edit_plan=edit_plan,
        needs_clarification=needs_clarification,
        version_number=current_version.version_number,
    )
