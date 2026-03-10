import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class CreateProjectRequest(BaseModel):
    project_id: str = Field(..., min_length=1, max_length=255)
    target_aspect_ratio: str | None = None
    language: str | None = None
    transcript: dict | None = None

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9 _-]+$", v):
            raise ValueError("project_id must contain only alphanumeric, spaces, hyphens, underscores")
        return v


class AssetOut(BaseModel):
    id: str
    project_id: str
    asset_type: str
    original_filename: str
    file_path: str
    duration_seconds: float | None
    width: int | None
    height: int | None
    format: str | None
    file_size_bytes: int | None
    metadata_extra: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectOut(BaseModel):
    id: str
    target_aspect_ratio: str | None
    language: str | None
    timeline: dict | None
    transcript: dict | None
    status: str
    created_at: datetime
    updated_at: datetime
    assets: list[AssetOut] = []

    model_config = {"from_attributes": True}


class ProjectListOut(BaseModel):
    id: str
    target_aspect_ratio: str | None
    language: str | None
    status: str
    asset_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TimelineOut(BaseModel):
    project_id: str
    timeline: dict | None


class EditRequest(BaseModel):
    prompt: str


class ProjectEditJobOut(BaseModel):
    id: int
    project_id: str
    prompt: str
    status: str
    timeline_before: dict | None
    timeline_after: dict | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}
