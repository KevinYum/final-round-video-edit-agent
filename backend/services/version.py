"""Version management service — list, get detail, revert."""

import copy

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from backend.models.project import Project
from backend.models.version import ConversationMessage, ProjectVersion


async def get_current_version(project_id: str, db: AsyncSession) -> ProjectVersion | None:
    """Get the current version for a project, or None if no versions exist."""
    result = await db.execute(
        select(ProjectVersion)
        .where(ProjectVersion.project_id == project_id, ProjectVersion.is_current == True)  # noqa: E712
    )
    return result.scalar_one_or_none()


async def ensure_version(project_id: str, timeline: dict | None, db: AsyncSession) -> ProjectVersion:
    """Get current version or create version 1 if none exists."""
    version = await get_current_version(project_id, db)
    if version:
        return version

    version = ProjectVersion(
        project_id=project_id,
        version_number=1,
        timeline_snapshot=copy.deepcopy(timeline),
        is_current=True,
    )
    db.add(version)
    await db.flush()
    return version


async def create_new_version(
    project_id: str, timeline: dict | None, db: AsyncSession
) -> ProjectVersion:
    """Create a new version, marking it current and un-marking the old one."""
    # Get the highest version number
    result = await db.execute(
        select(ProjectVersion)
        .where(ProjectVersion.project_id == project_id)
        .order_by(ProjectVersion.version_number.desc())
    )
    latest = result.scalar_one_or_none()
    next_number = (latest.version_number + 1) if latest else 1

    # Un-mark current
    if latest and latest.is_current:
        latest.is_current = False

    new_version = ProjectVersion(
        project_id=project_id,
        version_number=next_number,
        timeline_snapshot=copy.deepcopy(timeline),
        is_current=True,
    )
    db.add(new_version)
    await db.flush()
    return new_version


async def list_versions(project_id: str, db: AsyncSession) -> list[ProjectVersion]:
    result = await db.execute(
        select(ProjectVersion)
        .where(ProjectVersion.project_id == project_id)
        .order_by(ProjectVersion.version_number)
    )
    return list(result.scalars().all())


async def get_version_detail(
    project_id: str, version_number: int, db: AsyncSession
) -> ProjectVersion | None:
    result = await db.execute(
        select(ProjectVersion)
        .where(
            ProjectVersion.project_id == project_id,
            ProjectVersion.version_number == version_number,
        )
        .options(selectinload(ProjectVersion.messages))
    )
    return result.scalar_one_or_none()


async def revert_to_version(
    project_id: str, version_number: int, db: AsyncSession
) -> ProjectVersion | None:
    """Revert to a specific version: restore timeline, update is_current flags."""
    target = await get_version_detail(project_id, version_number, db)
    if not target:
        return None

    # Un-mark all versions as current
    result = await db.execute(
        select(ProjectVersion).where(ProjectVersion.project_id == project_id)
    )
    for v in result.scalars().all():
        v.is_current = False

    # Mark target as current
    target.is_current = True

    # Restore project timeline
    project = await db.get(Project, project_id)
    if project:
        project.timeline = copy.deepcopy(target.timeline_snapshot)
        flag_modified(project, "timeline")

    await db.flush()
    return target


async def get_conversation_history(version: ProjectVersion, db: AsyncSession) -> list[dict]:
    """Get conversation messages for a version as simple dicts."""
    result = await db.execute(
        select(ConversationMessage)
        .where(ConversationMessage.version_id == version.id)
        .order_by(ConversationMessage.sequence_number)
    )
    messages = result.scalars().all()
    history = []
    for m in messages:
        entry = {"role": m.role, "content": m.content}
        # Include edit plan in assistant messages so LLM sees its own prior plans
        if m.role == "assistant" and m.edit_plan:
            entry["edit_plan"] = m.edit_plan
        if m.role == "assistant" and m.needs_clarification:
            entry["needs_clarification"] = True
        history.append(entry)
    return history


async def add_message(
    version: ProjectVersion,
    role: str,
    content: str,
    edit_plan: dict | None,
    needs_clarification: bool,
    db: AsyncSession,
) -> ConversationMessage:
    """Add a conversation message to a version."""
    # Get next sequence number
    result = await db.execute(
        select(ConversationMessage)
        .where(ConversationMessage.version_id == version.id)
        .order_by(ConversationMessage.sequence_number.desc())
        .limit(1)
    )
    last = result.scalars().first()
    next_seq = (last.sequence_number + 1) if last else 1

    msg = ConversationMessage(
        version_id=version.id,
        role=role,
        content=content,
        edit_plan=edit_plan,
        needs_clarification=needs_clarification,
        sequence_number=next_seq,
    )
    db.add(msg)
    await db.flush()
    return msg
