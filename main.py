import asyncio
from fastapi import FastAPI
from contextlib import asynccontextmanager

from config import settings
from database import engine, Base

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)


@app.get("/health")
def health_check():
    return {"status": "ok", "version": settings.VERSION}
