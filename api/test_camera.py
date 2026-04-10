from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from schemas.parking import TestSnapshotCreate
from models.core import TestSnapshot, TestCamera, CameraStatus

router = APIRouter(prefix="/test", tags=["Camera Test API"])


@router.post("/screenshots")
def upload_screenshot_mock(data: TestSnapshotCreate, db: Session = Depends(get_db)):
    camera = db.query(TestCamera).filter(TestCamera.id == data.camera_id).first()
    if not camera:
        camera = TestCamera(
            id=data.camera_id, lat=67.67, lon=13.37, status=CameraStatus.ok
        )
        db.add(camera)
    else:
        camera.status = CameraStatus.ok

    snapshot = TestSnapshot(
        camera_id=data.camera_id,
        free_a=data.free_a,
        free_b=data.free_b,
        free_c=data.free_c,
        free_pickup=data.free_pickup,
    )
    db.add(snapshot)
    db.commit()

    return {"status": "ok", "snapshot_id": snapshot.id}


# TODO: замена на реальные данные
@router.get("/cameras")
def get_cameras_mock():
    return [
        {"id": 1, "name": "Camera 1", "lat": 55.75, "lon": 37.61, "status": "ok"},
        {
            "id": 2,
            "name": "Camera 2",
            "lat": 55.76,
            "lon": 37.62,
            "status": "camera_unreachable",
        },
    ]


# TODO: замена на реальные данные
@router.post("/batch-screenshots")
def upload_batch_screenshots_mock(data: list[TestSnapshotCreate]):
    return {"status": "ok", "processed_count": len(data)}
