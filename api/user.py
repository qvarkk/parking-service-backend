from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.core import UserRequest, TestSnapshot, TestCamera
from api.utils import get_client_ip
from schemas.parking import (
    ParkingSearchResponse,
    SearchParkingQueryParams,
)
from services.geo import resolve_address, calculate_distance

router = APIRouter(prefix="", tags=["User API"])


@router.get("/parking/search", response_model=ParkingSearchResponse)
def search_parking(
    request: Request,
    params: SearchParkingQueryParams = Depends(),
    db: Session = Depends(get_db),
):
    user_req = UserRequest(
        lat=params.lat,
        lon=params.lon,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        is_success=True,
    )
    db.add(user_req)
    db.commit()

    cameras = db.query(TestCamera).all()

    parkings = []
    total_free = 0

    for cam in cameras:
        dist = calculate_distance(params.lat, params.lon, cam.lat, cam.lon)
        if dist <= params.radius:
            latest_snapshot = (
                db.query(TestSnapshot)
                .filter(TestSnapshot.camera_id == cam.id)
                .order_by(TestSnapshot.created_at.desc())
                .first()
            )

            cam_total_free = 0
            if latest_snapshot:
                cam_total_free = latest_snapshot.free_spots_count

            parkings.append(
                {
                    "id": cam.id,
                    "name": cam.name or f"Камера {cam.id}",
                    "lat": cam.lat,
                    "lon": cam.lon,
                    "distance_m": round(dist, 1),
                    "free_spots_count": cam_total_free,
                }
            )
            total_free += cam_total_free

    parkings.sort(key=lambda x: x["distance_m"])

    return ParkingSearchResponse(
        total_free_in_radius=total_free, radius_m=params.radius, parkings=parkings
    )
