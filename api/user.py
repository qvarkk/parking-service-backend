from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.core import UserRequest, TestSnapshot, TestCamera
from schemas.parking import (
    GeoResolveRequest,
    GeoResolveResponse,
    ParkingSearchResponse,
    SearchParkingQueryParams,
)
from services.geo import resolve_address, calculate_distance

router = APIRouter(prefix="", tags=["User API"])


@router.get("/parking/search", response_model=ParkingSearchResponse)
def search_parking(
    params: SearchParkingQueryParams = Depends(), db: Session = Depends(get_db)
):
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

            distrib = {"A": 0, "B": 0, "C": 0, "PICKUP": 0}
            cam_total_free = 0

            if latest_snapshot:
                distrib = {
                    "A": latest_snapshot.free_a,
                    "B": latest_snapshot.free_b,
                    "C": latest_snapshot.free_c,
                    "PICKUP": latest_snapshot.free_pickup,
                }
                cam_total_free = (
                    latest_snapshot.free_a
                    + latest_snapshot.free_b
                    + latest_snapshot.free_c
                    + latest_snapshot.free_pickup
                )

            parkings.append(
                {
                    "id": cam.id,
                    "name": cam.name or f"Камера {cam.id}",
                    "lat": cam.lat,
                    "lon": cam.lon,
                    "distance_m": round(dist, 1),
                    "total_free": cam_total_free,
                    "distribution": distrib,
                }
            )
            total_free += cam_total_free

    parkings.sort(key=lambda x: x["distance_m"])

    return ParkingSearchResponse(
        total_free_in_radius=total_free, radius_m=params.radius, parkings=parkings
    )
