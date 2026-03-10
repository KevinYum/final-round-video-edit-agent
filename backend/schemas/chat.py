from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)


class ToolStep(BaseModel):
    step_number: int
    tool_name: str
    params: dict


class EditPlan(BaseModel):
    steps: list[ToolStep]
    summary: str


class ChatResponse(BaseModel):
    assistant_message: str
    edit_plan: EditPlan | None = None
    needs_clarification: bool = False
    version_number: int


class StepResult(BaseModel):
    step_number: int
    tool_name: str
    status: str  # "completed" | "failed"
    error: str | None = None


class ExecuteResponse(BaseModel):
    message: str
    version_number: int
    timeline: dict | None = None
    step_results: list[StepResult] = []
    success: bool = True
