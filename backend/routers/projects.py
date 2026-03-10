import asyncio
import copy
import os
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm.attributes import flag_modified
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import ASSET_DIR, get_db
from backend.models.project import Asset, Project, ProjectEditJob
from backend.schemas import (
    AssetOut,
    CreateProjectRequest,
    EditRequest,
    ProjectEditJobOut,
    ProjectListOut,
    ProjectOut,
    TimelineOut,
)
from backend.services.metadata import classify_asset_type, extract_metadata
from backend.services.render import render_timeline_to_file
from backend.services.timeline import (
    add_assets_to_timeline,
    create_empty_timeline,
)
from backend.services import metrics as metrics_service
from backend.services import version as version_service

EXPORT_DIR = ASSET_DIR.parent / "exports"

router = APIRouter(prefix="/api/projects", tags=["projects"])


# ── Projects ──────────────────────────────────────────────────────────


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(
    req: CreateProjectRequest, db: AsyncSession = Depends(get_db)
) -> ProjectOut:
    existing = await db.get(Project, req.project_id)
    if existing:
        raise HTTPException(status_code=409, detail="Project already exists")

    project = Project(
        id=req.project_id,
        target_aspect_ratio=req.target_aspect_ratio,
        language=req.language,
        timeline=create_empty_timeline(),
        transcript=req.transcript,
        status="created",
    )
    db.add(project)
    await metrics_service.increment("total_projects", db)
    await db.commit()

    result = await db.execute(
        select(Project).where(Project.id == req.project_id).options(selectinload(Project.assets))
    )
    return result.scalar_one()


@router.get("", response_model=list[ProjectListOut])
async def list_projects(db: AsyncSession = Depends(get_db)) -> list[ProjectListOut]:
    result = await db.execute(select(Project).options(selectinload(Project.assets)))
    projects = result.scalars().all()
    return [
        ProjectListOut(
            id=p.id,
            target_aspect_ratio=p.target_aspect_ratio,
            language=p.language,
            status=p.status,
            asset_count=len(p.assets),
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in projects
    ]


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)) -> ProjectOut:
    result = await db.execute(
        select(Project).where(Project.id == project_id).options(selectinload(Project.assets))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)) -> None:
    result = await db.execute(
        select(Project).where(Project.id == project_id).options(selectinload(Project.assets))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Remove asset files from disk
    project_dir = ASSET_DIR / project_id
    if project_dir.exists():
        shutil.rmtree(project_dir)

    await db.delete(project)
    await db.commit()


# ── Assets ────────────────────────────────────────────────────────────


@router.post("/{project_id}/assets", response_model=list[AssetOut])
async def load_assets(
    project_id: str,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
) -> list[AssetOut]:
    result = await db.execute(
        select(Project).where(Project.id == project_id).options(selectinload(Project.assets))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project_dir = ASSET_DIR / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    created_assets: list[Asset] = []
    timeline_entries: list[dict] = []

    for file in files:
        if not file.filename:
            continue

        asset_id = uuid.uuid4().hex
        asset_type = classify_asset_type(file.filename)
        ext = os.path.splitext(file.filename)[1]
        stored_name = f"{asset_id}{ext}"
        stored_path = project_dir / stored_name

        with open(stored_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        file_size = stored_path.stat().st_size
        meta = await extract_metadata(str(stored_path), asset_type)

        asset = Asset(
            id=asset_id,
            project_id=project_id,
            asset_type=asset_type,
            original_filename=file.filename,
            file_path=str(stored_path),
            duration_seconds=meta["duration_seconds"],
            width=meta["width"],
            height=meta["height"],
            format=meta["format"],
            file_size_bytes=file_size,
            metadata_extra=meta["metadata_extra"],
        )
        db.add(asset)
        created_assets.append(asset)

        timeline_entries.append(
            {
                "id": asset_id,
                "asset_type": asset_type,
                "original_filename": file.filename,
                "duration_seconds": meta["duration_seconds"],
                "width": meta["width"],
                "height": meta["height"],
                "format": meta["format"],
            }
        )

    # Auto-populate timeline only on first upload (empty timeline).
    # Subsequent assets are available via insert_clip/replace_clip in edit plans.
    timeline = copy.deepcopy(project.timeline) or create_empty_timeline()
    if not timeline.get("clips"):
        project.timeline = add_assets_to_timeline(timeline, timeline_entries)
        flag_modified(project, "timeline")
    project.status = "active"

    await db.commit()

    for asset in created_assets:
        await db.refresh(asset)

    return created_assets


@router.get("/{project_id}/assets", response_model=list[AssetOut])
async def list_assets(project_id: str, db: AsyncSession = Depends(get_db)) -> list[AssetOut]:
    result = await db.execute(
        select(Asset).where(Asset.project_id == project_id).order_by(Asset.created_at)
    )
    return result.scalars().all()


@router.get("/{project_id}/assets/{asset_id}/download")
async def download_asset(
    project_id: str, asset_id: str, db: AsyncSession = Depends(get_db)
) -> FileResponse:
    result = await db.execute(
        select(Asset).where(Asset.id == asset_id, Asset.project_id == project_id)
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    from pathlib import Path

    file_path = Path(asset.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(file_path, filename=asset.original_filename)


# ── Timeline ──────────────────────────────────────────────────────────


@router.get("/{project_id}/timeline", response_model=TimelineOut)
async def get_timeline(project_id: str, db: AsyncSession = Depends(get_db)) -> TimelineOut:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return TimelineOut(project_id=project.id, timeline=project.timeline)


# ── Export ────────────────────────────────────────────────────────────


@router.get("/{project_id}/export")
async def export_video(
    project_id: str, download: bool = False, db: AsyncSession = Depends(get_db)
) -> FileResponse:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    timeline = project.timeline
    if not timeline or not timeline.get("clips"):
        raise HTTPException(status_code=400, detail="No clips in timeline to export")

    # Get current version number for filename
    version = await version_service.get_current_version(project_id, db)
    version_num = version.version_number if version else 0

    # Build asset_id -> file_path mapping
    result = await db.execute(
        select(Asset).where(Asset.project_id == project_id)
    )
    assets = result.scalars().all()
    asset_paths = {a.id: a.file_path for a in assets}

    output_path = EXPORT_DIR / project_id / f"v{version_num}.mp4"

    # Render if not cached
    if not output_path.exists():
        try:
            await asyncio.to_thread(
                render_timeline_to_file, timeline, asset_paths, output_path
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    if download:
        await metrics_service.increment("export_count", db)
        await db.commit()

    return FileResponse(
        output_path,
        filename=f"{project_id}_v{version_num}.mp4",
        media_type="video/mp4",
    )


# ── Edit Jobs ─────────────────────────────────────────────────────────


@router.post("/{project_id}/edit", response_model=ProjectEditJobOut)
async def create_edit_job(
    project_id: str, req: EditRequest, db: AsyncSession = Depends(get_db)
) -> ProjectEditJobOut:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    job = ProjectEditJob(
        project_id=project_id,
        prompt=req.prompt,
        status="pending",
        timeline_before=copy.deepcopy(project.timeline),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@router.get("/{project_id}/jobs", response_model=list[ProjectEditJobOut])
async def list_edit_jobs(
    project_id: str, db: AsyncSession = Depends(get_db)
) -> list[ProjectEditJobOut]:
    result = await db.execute(
        select(ProjectEditJob)
        .where(ProjectEditJob.project_id == project_id)
        .order_by(ProjectEditJob.created_at.desc())
    )
    return result.scalars().all()
