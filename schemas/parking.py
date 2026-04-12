from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime
from models.core import CameraStatus, TripStatus


class ParkingItem(BaseModel):
    id: int
    name: str
    lat: float
    lon: float
    distance_m: float
    free_spots_count: int


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
    image_url: Optional[str] = None
    free_spots_count: int = 0


class TripSessionCreate(BaseModel):
    target_camera_id: int
    device_token: Optional[str] = None
    captcha_token: Optional[str] = None


class AdminCameraCreate(BaseModel):
    name: str
    lat: float
    lon: float
    status: Optional[CameraStatus] = CameraStatus.unknown


class AdminCameraStatusUpdate(BaseModel):
    status: CameraStatus


class CameraResponse(BaseModel):
    id: int
    name: str
    lat: float
    lon: float
    status: CameraStatus

    model_config = ConfigDict(from_attributes=True)


class SnapshotResponse(BaseModel):
    id: int
    image_url: Optional[str] = None
    free_spots_count: int
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


class AdminTripNotificationRequest(BaseModel):
    trip_id: int
    message: str
