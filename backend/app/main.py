import os
import json
import logging
from contextlib import asynccontextmanager
from typing import List, Set
from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.config import settings, runtime_config, get_esp32_url
from app.database import init_db, get_db
from app.models import SensorReading
from app.schemas import (
    ReadingCreate, ReadingResponse, LatestReadingResponse, IPUpdateRequest,
    ConfigResponse, StatsResponse
)
from app.crud import (
    create_reading, get_latest_reading, get_readings,
    get_recent_history, get_stats, clear_all_readings
)
from app.poller import poller

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("smartbin.main")

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        dead_connections = []
        payload_str = json.dumps(message)
        for connection in list(self.active_connections):
            try:
                await connection.send_text(payload_str)
            except Exception:
                dead_connections.append(connection)
        for dead in dead_connections:
            self.disconnect(dead)

manager = ConnectionManager()

# Hook poller to WebSocket broadcaster
async def poller_broadcast_callback(data: dict):
    await manager.broadcast(data)

poller.register_broadcaster(poller_broadcast_callback)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Database & Poller
    logger.info("Initializing Database...")
    init_db()
    logger.info("Starting ESP32 background poller...")
    await poller.start()
    yield
    # Shutdown
    logger.info("Shutting down ESP32 background poller...")
    await poller.stop()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="IoT Smart Waste Bin Monitoring Backend with FastAPI & PostgreSQL",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for dashboard flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Endpoints
@app.get("/api/readings/latest", response_model=LatestReadingResponse)
def read_latest_reading(db: Session = Depends(get_db)):
    reading = get_latest_reading(db)
    return LatestReadingResponse(
        reading=ReadingResponse.model_validate(reading) if reading else None,
        esp32_online=poller.esp32_online,
        esp32_target_url=get_esp32_url()
    )

@app.get("/api/readings", response_model=List[ReadingResponse])
def read_readings(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return get_readings(db, skip=skip, limit=limit)

@app.get("/api/readings/history", response_model=List[ReadingResponse])
def read_history(limit: int = 30, db: Session = Depends(get_db)):
    return get_recent_history(db, limit=limit)

@app.post("/api/readings", response_model=ReadingResponse)
async def add_reading(reading_in: ReadingCreate, db: Session = Depends(get_db)):
    reading = create_reading(db, reading_in)
    # Broadcast to dashboard
    broadcast_data = {
        "type": "new_reading",
        "data": {
            "id": reading.id,
            "timestamp": reading.timestamp.isoformat() if reading.timestamp else "",
            "distance_cm": reading.distance_cm,
            "fill_percentage": reading.fill_percentage,
            "status": reading.status,
            "is_valid": reading.is_valid,
            "source": reading.source,
            "esp32_online": poller.esp32_online
        }
    }
    await manager.broadcast(broadcast_data)
    return reading

@app.get("/api/stats", response_model=StatsResponse)
def read_stats(db: Session = Depends(get_db)):
    return get_stats(
        db,
        esp32_online=poller.esp32_online,
        target_url=get_esp32_url()
    )

@app.get("/api/config", response_model=ConfigResponse)
def read_config():
    return ConfigResponse(
        esp32_ip=runtime_config["esp32_ip"],
        esp32_port=runtime_config["esp32_port"],
        poll_interval=runtime_config["poll_interval"],
        polling_enabled=runtime_config["polling_enabled"],
        target_url=get_esp32_url()
    )

@app.post("/api/config/esp32-ip", response_model=ConfigResponse)
def update_esp32_ip(req: IPUpdateRequest):
    runtime_config["esp32_ip"] = req.esp32_ip.strip()
    if req.esp32_port:
        runtime_config["esp32_port"] = req.esp32_port
    logger.info(f"Updated ESP32 Target to: {get_esp32_url()}")
    return read_config()

@app.delete("/api/readings")
def clear_readings(db: Session = Depends(get_db)):
    deleted = clear_all_readings(db)
    return {"message": f"Deleted {deleted} readings from database."}

# WebSocket for real-time live updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, db: Session = Depends(get_db)):
    await manager.connect(websocket)
    try:
        # Immediately send current status on connect
        latest = get_latest_reading(db)
        if latest:
            initial_data = {
                "type": "initial_state",
                "data": {
                    "id": latest.id,
                    "timestamp": latest.timestamp.isoformat() if latest.timestamp else "",
                    "distance_cm": latest.distance_cm,
                    "fill_percentage": latest.fill_percentage,
                    "status": latest.status,
                    "is_valid": latest.is_valid,
                    "source": latest.source,
                    "esp32_online": poller.esp32_online
                }
            }
            await websocket.send_text(json.dumps(initial_data))
        while True:
            # Keep socket open and listen for ping / client commands
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

# Mount static files and serve frontend dashboard
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def serve_dashboard():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h1>Smart Bin Backend Running</h1><p>Static files missing.</p>")
