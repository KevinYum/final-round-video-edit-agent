import copy
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import ASSET_DIR, get_db
from backend.models.project import Project
from backend.schemas import RevertRequest, RollbackResponse, VersionDetailOut, VersionOut
from backend.schemas.version import ConversationMessageOut
from backend.services import metrics as metrics_service
from backend.services import version as version_service

logger = logging.getLogger(__name__)
EXPORT_DIR = ASSET_DIR.parent / "exports"

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
            executed=v.executed,
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
        executed=version.executed,
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

    await metrics_service.increment("undo_or_recovery_count", db)
    await db.commit()

    return VersionOut(
        version_number=version.version_number,
        timeline_snapshot=version.timeline_snapshot,
        is_current=version.is_current,
        executed=version.executed,
        created_at=version.created_at,
    )


@router.post("/{project_id}/rollback", response_model=RollbackResponse)
async def rollback_version(
    project_id: str, db: AsyncSession = Depends(get_db)
) -> RollbackResponse:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        target = await version_service.rollback(project_id, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await metrics_service.increment("undo_or_recovery_count", db)
    await db.commit()

    # Clean up stale export caches for deleted versions
    try:
        export_dir = EXPORT_DIR / project_id
        if export_dir.exists():
            for f in export_dir.iterdir():
                # Keep only exports for versions <= target
                if f.suffix == ".mp4":
                    # e.g. "v2.mp4" → version 2
                    try:
                        vnum = int(f.stem.lstrip("v"))
                        if vnum > target.version_number:
                            f.unlink()
                    except ValueError:
                        pass
    except Exception:
        logger.warning("Failed to clean export caches (non-fatal)", exc_info=True)

    return RollbackResponse(
        message=f"Rolled back to version {target.version_number}.",
        version_number=target.version_number,
        timeline=target.timeline_snapshot,
    )
