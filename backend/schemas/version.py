from datetime import datetime

from pydantic import BaseModel, Field


class ConversationMessageOut(BaseModel):
    role: str
    content: str
    edit_plan: dict | None = None
    needs_clarification: bool = False
    sequence_number: int
    created_at: datetime

    model_config = {"from_attributes": True}


class VersionOut(BaseModel):
    version_number: int
    timeline_snapshot: dict | None = None
    is_current: bool
    executed: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class VersionDetailOut(VersionOut):
    messages: list[ConversationMessageOut] = []


class RevertRequest(BaseModel):
    version_number: int = Field(..., ge=1)
