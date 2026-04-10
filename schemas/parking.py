from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from models.core import CameraStatus, TripStatus


class GeoResolveRequest(BaseModel):
    address: str


class GeoResolveResponse(BaseModel):
    lat: float
    lon: float


class ParkingItem(BaseModel):
    id: int
    name: str
    lat: float
    lon: float
    distance_m: float
    total_free: int
    distribution: dict


class ParkingSearchResponse(BaseModel):
    total_free_in_radius: int
    radius_m: int
    parkings: List[ParkingItem]


class TestSnapshotCreate(BaseModel):
    camera_id: int
    free_a: int = 0
    free_b: int = 0
    free_c: int = 0
    free_pickup: int = 0


class TripSessionCreate(BaseModel):
    target_lat: float
    target_lon: float
    device_token: Optional[str] = None


class TripSessionResponse(BaseModel):
    id: int
    status: TripStatus
    target_lat: float
    target_lon: float


class NotificationResponse(BaseModel):
    id: int
    session_id: int
    message: str
    is_read: bool


class NotificationReadRequest(BaseModel):
    notification_ids: List[int]
