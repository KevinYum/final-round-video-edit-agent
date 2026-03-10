from pydantic import BaseModel


class MetricsOut(BaseModel):
    total_projects: int = 0
    total_edit_requests: int = 0
    successful_edit_requests: int = 0
    avg_agent_latency_ms: float = 0.0
    clarification_count: int = 0
    export_count: int = 0
    undo_or_recovery_count: int = 0

    model_config = {"from_attributes": True}
