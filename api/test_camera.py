from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy.orm import Session
import shutil
import uuid
from pathlib import Path
from database import get_db
from schemas.parking import TestSnapshotCreate, SnapshotResponse
from models.core import TestSnapshot, TestCamera, CameraStatus
from services.parking_inference import count_parking_spots_from_image

router = APIRouter(prefix="/test", tags=["Camera Test API"])


@router.post("/mock-data", response_model=SnapshotResponse)
def upload_mock_data(data: TestSnapshotCreate, db: Session = Depends(get_db)):
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


@router.post("/screenshot", response_model=SnapshotResponse)
async def upload_screenshot(
    camera_id: int = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    camera = db.query(TestCamera).filter(TestCamera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    upload_dir = Path("cam-images")
    upload_dir.mkdir(exist_ok=True)

    file_ext = Path(image.filename).suffix or ".jpg"
    unique_filename = f"upload_{camera_id}_{uuid.uuid4().hex}{file_ext}"
    file_path = upload_dir / unique_filename

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    try:
        ai_result = count_parking_spots_from_image(file_path)

        camera.status = CameraStatus.ok

        snapshot = TestSnapshot(
            camera_id=camera_id,
            image_url=str(file_path),
            free_spots_count=ai_result.free_spots,
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)

        return snapshot
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"AI processing failed: {str(e)}")
