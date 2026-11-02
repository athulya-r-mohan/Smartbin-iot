import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Smart Waste Bin IoT System"
    ESP32_IP: str = "192.168.1.100"
    ESP32_PORT: int = 80
    POLL_INTERVAL_SECONDS: float = 2.0
    DATABASE_URL: str = "postgresql://smartbin:smartbin123@localhost:5432/smartbindb"
    
    # Thresholds
    MEDIUM_THRESHOLD: int = 50
    FULL_THRESHOLD: int = 75
    DANGER_THRESHOLD: int = 80

    model_config = SettingsConfigDict(env_file=".env", extra="allow")

settings = Settings()

# Runtime mutable state for college hotspot IP updates without restarting
runtime_config = {
    "esp32_ip": settings.ESP32_IP,
    "esp32_port": settings.ESP32_PORT,
    "poll_interval": settings.POLL_INTERVAL_SECONDS,
    "polling_enabled": True
}

def get_esp32_url() -> str:
    ip = runtime_config["esp32_ip"].strip()
    port = runtime_config["esp32_port"]
    if ip.startswith("http://") or ip.startswith("https://"):
        base = ip
    else:
        base = f"http://{ip}:{port}" if port != 80 else f"http://{ip}"
    return f"{base.rstrip('/')}/data"
