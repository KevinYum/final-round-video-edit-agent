"""Metrics service — atomic increment/record helpers for global metrics."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.metrics import GlobalMetrics
from backend.schemas.metrics import MetricsOut


async def _get_or_create(db: AsyncSession) -> GlobalMetrics:
    """Get the singleton metrics row, creating it if absent."""
    result = await db.execute(select(GlobalMetrics).where(GlobalMetrics.id == 1))
    row = result.scalar_one_or_none()
    if row is None:
        row = GlobalMetrics(id=1)
        db.add(row)
        await db.flush()
    return row


async def increment(field: str, db: AsyncSession, amount: int = 1) -> None:
    """Atomically increment a counter field by *amount*."""
    row = await _get_or_create(db)
    current = getattr(row, field)
    setattr(row, field, current + amount)


async def record_latency(latency_ms: float, db: AsyncSession) -> None:
    """Record an LLM call latency (updates total_llm_calls + cumulative_latency_ms)."""
    row = await _get_or_create(db)
    row.total_llm_calls += 1
    row.cumulative_latency_ms += latency_ms


async def get_metrics(db: AsyncSession) -> MetricsOut:
    """Return all metrics, computing avg_agent_latency_ms from raw values."""
    row = await _get_or_create(db)
    avg_latency = 0.0
    if row.total_llm_calls > 0:
        avg_latency = round(row.cumulative_latency_ms / row.total_llm_calls, 1)

    return MetricsOut(
        total_projects=row.total_projects,
        total_edit_requests=row.total_edit_requests,
        successful_edit_requests=row.successful_edit_requests,
        avg_agent_latency_ms=avg_latency,
        clarification_count=row.clarification_count,
        export_count=row.export_count,
        undo_or_recovery_count=row.undo_or_recovery_count,
    )
