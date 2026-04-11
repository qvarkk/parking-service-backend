import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from api.limiter import limiter

from config import settings
from database import engine, Base
from api import user, trip, test_camera, admin_auth
from services.scheduler import background_scheduler
from scripts.seed_db import seed_database

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_database()
    task = asyncio.create_task(background_scheduler())
    yield
    task.cancel()


app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.include_router(user.router)
app.include_router(trip.router)
app.include_router(test_camera.router)
app.include_router(admin_auth.router)


@app.get("/health")
def health_check():
    return {"status": "ok", "version": settings.VERSION}
