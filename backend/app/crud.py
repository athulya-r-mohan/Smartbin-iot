from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime

from app.models import SensorReading
from app.schemas import ReadingCreate
from app.config import settings

def calculate_status(fill: int, is_valid: bool = True) -> str:
    if not is_valid:
        return "INVALID"
    if fill >= settings.DANGER_THRESHOLD:
        return "DANGER"
    elif fill >= settings.FULL_THRESHOLD:
        return "FULL"
    elif fill >= settings.MEDIUM_THRESHOLD:
        return "MEDIUM"
    else:
        return "LOW"

def create_reading(db: Session, reading_in: ReadingCreate) -> SensorReading:
    status = calculate_status(reading_in.fill_percentage, reading_in.is_valid)
    db_obj = SensorReading(
        distance_cm=reading_in.distance_cm,
        fill_percentage=reading_in.fill_percentage,
        status=status,
        is_valid=reading_in.is_valid,
        source=reading_in.source or "ESP32"
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def get_latest_reading(db: Session) -> Optional[SensorReading]:
    return db.query(SensorReading).order_by(SensorReading.id.desc()).first()

def get_readings(db: Session, skip: int = 0, limit: int = 100) -> List[SensorReading]:
    return db.query(SensorReading).order_by(SensorReading.id.desc()).offset(skip).limit(limit).all()

def get_recent_history(db: Session, limit: int = 30) -> List[SensorReading]:
    # Return oldest to newest for charting
    readings = db.query(SensorReading).order_by(SensorReading.id.desc()).limit(limit).all()
    readings.reverse()
    return readings

def get_stats(db: Session, esp32_online: bool, target_url: str):
    total = db.query(SensorReading).count()
    latest = get_latest_reading(db)
    
    danger_count = db.query(SensorReading).filter(SensorReading.status == "DANGER").count()
    full_count = db.query(SensorReading).filter(SensorReading.status == "FULL").count()
    medium_count = db.query(SensorReading).filter(SensorReading.status == "MEDIUM").count()
    low_count = db.query(SensorReading).filter(SensorReading.status == "LOW").count()

    return {
        "total_readings": total,
        "current_fill": latest.fill_percentage if latest else None,
        "current_status": latest.status if latest else "UNKNOWN",
        "current_distance": latest.distance_cm if latest else None,
        "last_updated": latest.timestamp if latest else None,
        "danger_count": danger_count,
        "full_count": full_count,
        "medium_count": medium_count,
        "low_count": low_count,
        "esp32_online": esp32_online,
        "esp32_target_url": target_url,
    }

def clear_all_readings(db: Session) -> int:
    num_deleted = db.query(SensorReading).delete()
    db.commit()
    return num_deleted

