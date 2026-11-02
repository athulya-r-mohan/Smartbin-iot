import asyncio
import logging
import httpx
from datetime import datetime
from typing import Optional, Callable, Awaitable

from app.config import runtime_config, get_esp32_url
from app.database import SessionLocal
from app.schemas import ReadingCreate
from app.crud import create_reading

logger = logging.getLogger("smartbin.poller")

class ESP32Poller:
    def __init__(self):
        self.is_running = False
        self.esp32_online = False
        self.last_poll_time: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self.broadcast_callback: Optional[Callable[[dict], Awaitable[None]]] = None
        self._task: Optional[asyncio.Task] = None

    def register_broadcaster(self, callback: Callable[[dict], Awaitable[None]]):
        self.broadcast_callback = callback

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("ESP32 Background Poller started.")

    async def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("ESP32 Background Poller stopped.")

    async def _poll_loop(self):
        while self.is_running:
            if not runtime_config.get("polling_enabled", True):
                await asyncio.sleep(1.0)
                continue

            target_url = get_esp32_url()
            interval = float(runtime_config.get("poll_interval", 2.0))

            try:
                async with httpx.AsyncClient(timeout=2.5) as client:
                    response = await client.get(target_url)
                    if response.status_code == 200:
                        payload = response.json()
                        self.esp32_online = True
                        self.last_error = None
                        self.last_poll_time = datetime.now()

                        # Parse payload
                        is_valid = bool(payload.get("valid", False))
                        distance = float(payload.get("distance", -1.0))
                        fill = int(payload.get("fill", 0))

                        # Save to database
                        db = SessionLocal()
                        try:
                            reading = create_reading(
                                db=db,
                                reading_in=ReadingCreate(
                                    distance_cm=distance,
                                    fill_percentage=fill,
                                    is_valid=is_valid,
                                    source="ESP32"
                                )
                            )
                            # Prepare broadcast packet
                            broadcast_data = {
                                "type": "new_reading",
                                "data": {
                                    "id": reading.id,
                                    "timestamp": reading.timestamp.isoformat() if reading.timestamp else datetime.now().isoformat(),
                                    "distance_cm": reading.distance_cm,
                                    "fill_percentage": reading.fill_percentage,
                                    "status": reading.status,
                                    "is_valid": reading.is_valid,
                                    "source": reading.source,
                                    "esp32_online": True
                                }
                            }
                            if self.broadcast_callback:
                                await self.broadcast_callback(broadcast_data)
                        finally:
                            db.close()
                    else:
                        self.esp32_online = False
                        self.last_error = f"HTTP {response.status_code}"
            except Exception as e:
                # Normal when ESP32 is offline or not yet connected to the local network
                self.esp32_online = False
                self.last_error = str(e)

            await asyncio.sleep(interval)

poller = ESP32Poller()

