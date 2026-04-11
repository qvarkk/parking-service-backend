from pydantic import BaseModel, ConfigDict, Field
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


class SearchParkingQueryParams(BaseModel):
    lat: float = Field(..., description="Широта")
    lon: float = Field(..., description="Долгота")
    radius: int = Field(1000, ge=100, le=10000, description="Радиус поиска в метрах")


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
    target_camera_id: int
    device_token: Optional[str] = None
    captcha_token: Optional[str] = None


class CameraResponse(BaseModel):
    id: int
    name: str
    lat: float
    lon: float
    status: CameraStatus

    model_config = ConfigDict(from_attributes=True)


class SnapshotResponse(BaseModel):
    id: int
    free_a: int
    free_b: int
    free_c: int
    free_pickup: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminCameraResponse(CameraResponse):
    latest_snapshot: Optional[SnapshotResponse] = None


class TripSessionResponse(BaseModel):
    id: int
    status: TripStatus
    camera: CameraResponse

    model_config = ConfigDict(from_attributes=True)


class NotificationResponse(BaseModel):
    id: int
    session_id: int
    message: str
    is_read: bool


class NotificationReadRequest(BaseModel):
    notification_ids: List[int]
