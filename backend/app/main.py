from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_models
from app.routers import auth, jobs, uploads

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.environment == "development":
        # In production, run Alembic migrations at deploy time instead.
        await init_models()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(uploads.router)
app.include_router(jobs.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
