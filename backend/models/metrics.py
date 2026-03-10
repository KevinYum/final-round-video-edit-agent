from sqlalchemy import Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class GlobalMetrics(Base):
    __tablename__ = "global_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    total_projects: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_edit_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_edit_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_llm_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cumulative_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    clarification_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    export_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    undo_or_recovery_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
