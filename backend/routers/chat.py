from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas import ChatRequest, ChatResponse, ExecuteResponse
from backend.services.chat import handle_chat
from backend.services.execute import execute_plan

router = APIRouter(prefix="/api/projects", tags=["chat"])


@router.post("/{project_id}/chat", response_model=ChatResponse)
async def chat(
    project_id: str,
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    try:
        return await handle_chat(
            project_id=project_id,
            message=req.message,
            db=db,
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        if "OPENAI_API_KEY" in msg:
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")
        raise HTTPException(status_code=400, detail=msg)


@router.post("/{project_id}/execute", response_model=ExecuteResponse)
async def execute(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> ExecuteResponse:
    try:
        return await execute_plan(project_id=project_id, db=db)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        if "no plan" in msg.lower():
            raise HTTPException(status_code=400, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
