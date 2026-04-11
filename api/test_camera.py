from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from schemas.parking import TestSnapshotCreate, SnapshotResponse
from models.core import TestSnapshot, TestCamera, CameraStatus

router = APIRouter(prefix="/test", tags=["Camera Test API"])


@router.post("/screenshots", response_model=SnapshotResponse)
def upload_screenshot_mock(data: TestSnapshotCreate, db: Session = Depends(get_db)):
    camera = db.query(TestCamera).filter(TestCamera.id == data.camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    camera.status = CameraStatus.ok

    snapshot = TestSnapshot(
        camera_id=data.camera_id,
        free_spots_count=data.free_spots_count,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    return snapshot


@router.post("/batch-screenshots", response_model=list[SnapshotResponse])
def upload_batch_screenshots_mock(
    data: list[TestSnapshotCreate], db: Session = Depends(get_db)
):
    camera_ids = {item.camera_id for item in data}
    cameras = db.query(TestCamera).filter(TestCamera.id.in_(camera_ids)).all()
    camera_map = {c.id: c for c in cameras}

    if len(camera_map) != len(camera_ids):
        missing_ids = [cid for cid in camera_ids if cid not in camera_map]
        raise HTTPException(status_code=404, detail=f"Cameras not found: {missing_ids}")

    snapshots = []
    for item in data:
        camera = camera_map[item.camera_id]
        camera.status = CameraStatus.ok

        snapshot = TestSnapshot(
            camera_id=item.camera_id,
            free_spots_count=item.free_spots_count,
        )
        db.add(snapshot)
        snapshots.append(snapshot)

    db.commit()
    for s in snapshots:
        db.refresh(s)

    return snapshots
