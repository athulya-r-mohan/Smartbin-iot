from sqlalchemy import Column, Integer, Float, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.database import Base

class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    distance_cm = Column(Float, nullable=False)
    fill_percentage = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, index=True)  # LOW, MEDIUM, FULL, DANGER
    is_valid = Column(Boolean, default=True)
    source = Column(String(50), default="ESP32")  # ESP32, SIMULATOR, MANUAL

    def __repr__(self):
        return f"<SensorReading id={self.id} fill={self.fill_percentage}% status={self.status}>"

