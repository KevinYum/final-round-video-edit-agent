"""Execute service — applies the current edit plan by running tool executors."""

import copy
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from backend.database import ASSET_DIR
from backend.models.project import Asset, Project
from backend.models.version import ConversationMessage, ProjectVersion
from backend.schemas.chat import ExecuteResponse, StepResult
from backend.services import version as version_service
from backend.services.tool_executors import (
    TOOL_REGISTRY,
    ToolContext,
    ToolExecutionError,
    recompute_timeline,
)

EXPORT_DIR = ASSET_DIR.parent / "exports"

logger = logging.getLogger(__name__)


async def _get_pending_plan(version: ProjectVersion, db: AsyncSession) -> dict | None:
    """Find the latest edit_plan from the current version's messages."""
    result = await db.execute(
        select(ConversationMessage)
        .where(
            ConversationMessage.version_id == version.id,
            ConversationMessage.role == "assistant",
            ConversationMessage.edit_plan.isnot(None),
            ConversationMessage.needs_clarification == False,  # noqa: E712
        )
        .order_by(ConversationMessage.sequence_number.desc())
        .limit(1)
    )
    msg = result.scalars().first()
    return msg.edit_plan if msg else None


async def execute_plan(project_id: str, db: AsyncSession) -> ExecuteResponse:
    """Execute the pending edit plan step by step.

    1. Load project + assets, get current version + pending plan.
    2. Deep-copy timeline, run each step sequentially.
    3. On failure: return immediately with success=False, no version bump.
    4. On success: update project.timeline, create new version, commit.
    """
    # Load project with assets
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id)
        .options(selectinload(Project.assets))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise ValueError(f"Project not found: {project_id}")

    # Get current version
    current_version = await version_service.get_current_version(project_id, db)
    if not current_version:
        raise ValueError("No plan to execute: no version exists")

    # Get pending plan
    plan = await _get_pending_plan(current_version, db)
    if not plan:
        raise ValueError("No plan to execute: no ready edit plan in current version")

    steps = plan.get("steps", [])
    if not steps:
        raise ValueError("Edit plan has no steps")

    # Build context for tool executors
    assets_info = [
        {
            "id": a.id,
            "asset_type": a.asset_type,
            "original_filename": a.original_filename,
            "duration_seconds": a.duration_seconds,
            "width": a.width,
            "height": a.height,
            "format": a.format,
        }
        for a in project.assets
    ]
    context = ToolContext(project_id=project_id, project_assets=assets_info)

    # Deep copy timeline so we don't mutate on failure
    timeline = copy.deepcopy(project.timeline)
    step_results: list[StepResult] = []

    # Execute each step sequentially
    for step in steps:
        step_num = step.get("step_number", len(step_results) + 1)
        tool_name = step.get("tool_name", "")
        params = step.get("params", {})

        executor = TOOL_REGISTRY.get(tool_name)
        if not executor:
            step_results.append(StepResult(
                step_number=step_num,
                tool_name=tool_name,
                status="failed",
                error=f"Unknown tool: {tool_name}",
            ))
            return ExecuteResponse(
                message=f"Execution failed at step {step_num}: unknown tool '{tool_name}'.",
                version_number=current_version.version_number,
                timeline=project.timeline,
                step_results=step_results,
                success=False,
            )

        try:
            executor(timeline, params, context)
            step_results.append(StepResult(
                step_number=step_num,
                tool_name=tool_name,
                status="completed",
            ))
        except ToolExecutionError as e:
            step_results.append(StepResult(
                step_number=step_num,
                tool_name=tool_name,
                status="failed",
                error=str(e),
            ))
            return ExecuteResponse(
                message=f"Execution failed at step {step_num} ({tool_name}): {e}",
                version_number=current_version.version_number,
                timeline=project.timeline,
                step_results=step_results,
                success=False,
            )
        except Exception as e:
            logger.exception(f"Unexpected error in step {step_num} ({tool_name})")
            step_results.append(StepResult(
                step_number=step_num,
                tool_name=tool_name,
                status="failed",
                error=f"Internal error: {e}",
            ))
            return ExecuteResponse(
                message=f"Execution failed at step {step_num} ({tool_name}): internal error.",
                version_number=current_version.version_number,
                timeline=project.timeline,
                step_results=step_results,
                success=False,
            )

    # All steps succeeded — recompute timeline positions
    recompute_timeline(timeline)

    # Generate new clip IDs for version isolation (supports rollback)
    for clip in timeline.get("clips", []):
        clip["id"] = f"clip-{uuid.uuid4().hex[:8]}"

    # Handle aspect ratio change if a tool set it
    pending_ratio = timeline.pop("_pending_aspect_ratio", None)
    if pending_ratio:
        project.target_aspect_ratio = pending_ratio

    # Update project timeline
    project.timeline = timeline
    flag_modified(project, "timeline")

    # Update current version's snapshot and mark as executed
    current_version.timeline_snapshot = copy.deepcopy(timeline)
    current_version.executed = True
    flag_modified(current_version, "timeline_snapshot")

    await db.commit()

    # Delete stale cached render so export endpoint re-renders with updated timeline
    version_num = current_version.version_number
    try:
        output_path = EXPORT_DIR / project_id / f"v{version_num}.mp4"
        if output_path.exists():
            output_path.unlink()
    except Exception:
        logger.warning("Failed to delete stale export cache (non-fatal)", exc_info=True)

    return ExecuteResponse(
        message=f"Plan executed successfully (v{current_version.version_number}).",
        version_number=current_version.version_number,
        timeline=timeline,
        step_results=step_results,
        success=True,
    )
