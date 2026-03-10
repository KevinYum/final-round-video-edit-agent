"""Execute service — applies the current edit plan, creating a new version.

For now this creates a version snapshot. Actual MoviePy-based tool execution
will be added in a future version — each step's tool_name(**params) will be
called sequentially to mutate the timeline.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.project import Project
from backend.models.version import ConversationMessage, ProjectVersion
from backend.schemas.chat import ExecuteResponse
from backend.services import version as version_service


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
    """Execute the pending edit plan for a project.

    1. Find current version and its latest ready plan.
    2. Create a new version with timeline snapshot.
    3. Return the new version info.

    Actual tool execution (MoviePy calls) will be added later —
    each step will be invoked as tool_name(**step.params).
    """
    # Load project
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

    # Create new version (snapshot current timeline)
    new_version = await version_service.create_new_version(
        project_id, project.timeline, db
    )

    await db.commit()

    return ExecuteResponse(
        message=f"Plan executed. Created version {new_version.version_number}.",
        version_number=new_version.version_number,
        timeline=project.timeline,
    )
