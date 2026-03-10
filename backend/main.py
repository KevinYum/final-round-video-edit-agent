from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.database import engine
from backend.models import Base
from backend.routers import chat, projects, versions


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="Video Edit Agent",
    description="Upload and edit videos using natural language",
    version="0.6.4",
    lifespan=lifespan,
)

app.include_router(projects.router)
app.include_router(chat.router)
app.include_router(versions.router)
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
