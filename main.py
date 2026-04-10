from fastapi import FastAPI

from config import settings
from database import engine, Base
from api import user, trip, test_camera, admin_auth

Base.metadata.create_all(bind=engine)


app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)

app.include_router(user.router)
app.include_router(trip.router)
app.include_router(test_camera.router)
app.include_router(admin_auth.router)


@app.get("/health")
def health_check():
    return {"status": "ok", "version": settings.VERSION}
