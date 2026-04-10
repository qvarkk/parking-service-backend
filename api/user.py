from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.core import UserRequest, TestSnapshot
from schemas.parking import GeoResolveRequest, GeoResolveResponse, ParkingSearchResponse
from services.geo import resolve_address

router = APIRouter(prefix="", tags=["User API"])


@router.post("/geo/resolve", response_model=GeoResolveResponse)
def resolve_geo(req: GeoResolveRequest, db: Session = Depends(get_db)):
    lat, lon = resolve_address(req.address)

    user_req = UserRequest(
        query_address=req.address, resolved_lat=lat, resolved_lon=lon
    )
    db.add(user_req)
    db.commit()

    return GeoResolveResponse(lat=lat, lon=lon)


# TODO: замена на реальные данные
@router.get("/parking/search", response_model=ParkingSearchResponse)
def search_parking(
    lat: float, lon: float, radius: int = 1000, db: Session = Depends(get_db)
):
    mock_parkings = [
        {
            "id": 1,
            "name": "Парковка 1",
            "lat": lat + 0.002,
            "lon": lon + 0.001,
            "distance_m": 250.0,
            "total_free": 15,
            "distribution": {"A": 5, "B": 10, "C": 0, "PICKUP": 0},
        },
        {
            "id": 2,
            "name": "Парковка 2",
            "lat": lat - 0.001,
            "lon": lon - 0.003,
            "distance_m": 420.0,
            "total_free": 42,
            "distribution": {"A": 12, "B": 20, "C": 10, "PICKUP": 0},
        },
        {
            "id": 3,
            "name": "Парковка 3",
            "lat": lat + 0.004,
            "lon": lon + 0.005,
            "distance_m": 750.0,
            "total_free": 4,
            "distribution": {"A": 0, "B": 0, "C": 0, "PICKUP": 4},
        },
    ]

    total_free = sum(p["total_free"] for p in mock_parkings)

    return ParkingSearchResponse(
        total_free_in_radius=total_free, radius_m=radius, parkings=mock_parkings
    )
