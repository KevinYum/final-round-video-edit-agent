import copy

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.project import Project
from backend.schemas import RevertRequest, VersionDetailOut, VersionOut
from backend.schemas.version import ConversationMessageOut
from backend.services import version as version_service

router = APIRouter(prefix="/api/projects", tags=["versions"])


@router.get("/{project_id}/versions", response_model=list[VersionOut])
async def list_versions(
    project_id: str, db: AsyncSession = Depends(get_db)
) -> list[VersionOut]:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    versions = await version_service.list_versions(project_id, db)
    return [
        VersionOut(
            version_number=v.version_number,
            timeline_snapshot=v.timeline_snapshot,
            is_current=v.is_current,
            created_at=v.created_at,
        )
        for v in versions
    ]


@router.get("/{project_id}/versions/{version_number}", response_model=VersionDetailOut)
async def get_version(
    project_id: str, version_number: int, db: AsyncSession = Depends(get_db)
) -> VersionDetailOut:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    version = await version_service.get_version_detail(project_id, version_number, db)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    return VersionDetailOut(
        version_number=version.version_number,
        timeline_snapshot=version.timeline_snapshot,
        is_current=version.is_current,
        created_at=version.created_at,
        messages=[
            ConversationMessageOut(
                role=m.role,
                content=m.content,
                edit_plan=m.edit_plan,
                needs_clarification=m.needs_clarification,
                sequence_number=m.sequence_number,
                created_at=m.created_at,
            )
            for m in version.messages
        ],
    )


@router.post("/{project_id}/versions/revert", response_model=VersionOut)
async def revert_version(
    project_id: str,
    req: RevertRequest,
    db: AsyncSession = Depends(get_db),
) -> VersionOut:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    version = await version_service.revert_to_version(project_id, req.version_number, db)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    await db.commit()

    return VersionOut(
        version_number=version.version_number,
        timeline_snapshot=version.timeline_snapshot,
        is_current=version.is_current,
        created_at=version.created_at,
    )
