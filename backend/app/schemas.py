from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional

class ESP32Payload(BaseModel):
    valid: bool
    distance: float
    fill: int
    danger: Optional[bool] = False

class ReadingCreate(BaseModel):
    distance_cm: float
    fill_percentage: int
    is_valid: bool = True
    source: Optional[str] = "ESP32_DIRECT"
    api_key: Optional[str] = None

class ReadingResponse(BaseModel):
    id: int
    timestamp: datetime
    distance_cm: float
    fill_percentage: int
    status: str
    is_valid: bool
    source: str

    model_config = ConfigDict(from_attributes=True)

class LatestReadingResponse(BaseModel):
    reading: Optional[ReadingResponse] = None
    esp32_online: bool
    esp32_target_url: str

class IPUpdateRequest(BaseModel):
    esp32_ip: str = Field(..., description="ESP32 IP address or hostname, e.g. 192.168.43.50")
    esp32_port: Optional[int] = Field(80, description="HTTP Port for ESP32 web server")

class ConfigResponse(BaseModel):
    esp32_ip: str
    esp32_port: int
    poll_interval: float
    polling_enabled: bool
    target_url: str

class StatsResponse(BaseModel):
    total_readings: int
    current_fill: Optional[int] = None
    current_status: Optional[str] = "UNKNOWN"
    current_distance: Optional[float] = None
    last_updated: Optional[datetime] = None
    danger_count: int = 0
    full_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    esp32_online: bool = False
    esp32_target_url: str
