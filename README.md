# ♻️ Smart Waste Bin IoT Monitoring System

An end-to-end IoT monitoring solution for ultrasonic smart waste bins. Integrates seamlessly with your working ESP32 sketch **without requiring any changes or re-flashing of your Arduino code**.

---

## 📌 Architecture Overview

```mermaid
flowchart LR
    ESP32["ESP32 Smart Bin\n(WiFi / Port 80)"] -->|"GET /data\n(Background Poller)"| FastAPI["FastAPI Backend\n(Port 8000)"]
    Simulator["Hardware Simulator\n(simulator.py)" ] -.->|"POST /api/readings"| FastAPI
    FastAPI -->|"Store readings & timestamps"| Postgres[("PostgreSQL 16\n(Port 5432)")]
    FastAPI -->|"WebSocket /ws\nReal-time push"| Dashboard["Web Dashboard\n(HTML5 / CSS / JS)"]
    Dashboard -->|"AudioContext Alert"| Sound["Sound Alarm (>= 80%)"]
```

### Fill Level Status Categories
- 🟢 **LOW**: `0% – 49%` (Normal operating capacity)
- 🟡 **MEDIUM**: `50% – 74%` (Waste accumulating)
- 🟠 **FULL**: `75% – 79%` (Bin nearly full)
- 🔴 **DANGER**: `≥ 80%` (Urgent: triggers visual danger banner + Web Audio browser alarm)

---

## 🚀 Key Features

1. **Zero Modifications to Arduino Sketch**:
   - The ESP32 sketch hosts a web server with a `/data` JSON endpoint.
   - The FastAPI backend continuously polls `http://<ESP32_IP>/data` via an asynchronous background task.
2. **Instant Hotspot / College WiFi IP Switcher**:
   - Easily change your ESP32 target IP from the **live web dashboard** or via `.env` without restarting or rebuilding containers when switching between home WiFi and your phone's mobile hotspot.
3. **Real-time Live Web Dashboard**:
   - Visual 3D-styled animated bin fill level with liquid waves.
   - Live percentage, distance in cm, status pill, and timestamp.
   - Built-in Web Audio API tone generator (no audio files needed, works reliably on all modern browsers).
4. **PostgreSQL Time-Series Logging**:
   - Sensor readings (distance, fill %, status, timestamp, validity) are saved to PostgreSQL.
   - Interactive historical trends chart powered by Chart.js.
5. **Full Testing & Simulation Suite**:
   - Automated pytest test suite covering all endpoints, status thresholds, and WebSocket events.
   - Python hardware simulator (`simulator.py`) for offline testing when the physical ESP32 is not powered.

---

## 📂 Project Structure

```text
SmartBinProject/
├── SmartBinProject.ino/
│   └── SmartBinProject.ino.ino    # Working ESP32 sketch (UNTOUCHED)
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py              # Configuration & hotspot IP manager
│   │   ├── crud.py                # Database queries & status calculations
│   │   ├── database.py            # SQLAlchemy setup with Postgres + SQLite fallback
│   │   ├── main.py                # FastAPI endpoints & WebSocket hub
│   │   ├── models.py              # PostgreSQL SensorReading model
│   │   ├── poller.py              # Async ESP32 background poller
│   │   ├── schemas.py             # Pydantic v2 schemas
│   │   └── static/                # Responsive Web Dashboard
│   │       ├── app.js             # WebSocket listener & Web Audio alarm
│   │       ├── index.html         # Live dashboard layout
│   │       └── style.css          # Responsive design & theme styles
│   ├── tests/
│   │   ├── __init__.py
│   │   └── test_api.py            # Automated pytest test suite
│   ├── simulator.py               # Hardware simulator for testing without ESP32
│   ├── requirements.txt           # Python dependencies
│   └── Dockerfile                 # Backend container image definition
├── docker-compose.yml             # Orchestration for FastAPI + PostgreSQL
├── .env.example                   # Environment configuration template
├── .env                           # Active configuration file
└── README.md                      # Documentation & instructions
```

---

## ⚙️ Quick Start with Docker & Docker Compose

### 1. Configure the ESP32 IP
Open `.env` (or copy `.env.example` to `.env`):
```env
ESP32_IP=192.168.1.100
ESP32_PORT=80
POLL_INTERVAL_SECONDS=2.0
```

### 2. Start Services
From the project root:
```bash
docker compose up --build
```
This starts:
- **PostgreSQL 16** on `localhost:5432`
- **FastAPI Backend & Dashboard** on `http://localhost:8000`

### 3. Open the Web Dashboard
Navigate to [http://localhost:8000](http://localhost:8000) in your web browser.
Click **"🔔 Enable Sound Alerts"** on the dashboard header to authorize browser audio playback.

---

## 💻 Local Development Setup (Without Docker)

### 1. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure Database
- If PostgreSQL is running locally, ensure `.env` contains:
  ```env
  DATABASE_URL=postgresql://smartbin:smartbin123@localhost:5432/smartbindb
  ```
- *Note:* If PostgreSQL is not active, the backend automatically provides a seamless fallback to a local SQLite database (`sqlite:///./smartbin.db`) so development and testing are never blocked.

### 3. Run FastAPI Application
From the `backend` folder:
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Open [http://localhost:8000](http://localhost:8000).

---

## 📱 Mobile Hotspot & College WiFi Setup

When taking your ESP32 to college and connecting to a phone's mobile hotspot:
1. Turn on your mobile hotspot and note the ESP32's assigned IP from the Arduino Serial Monitor (or your phone's connected devices screen).
2. Open the dashboard at `http://localhost:8000`.
3. In the **"WiFi / College Hotspot Config"** card on the right:
   - Enter your new ESP32 IP (e.g. `192.168.43.50`).
   - Click **"Save Target IP"**.
4. The background poller immediately begins fetching from your new IP without restarting Docker or changing files!

---

## 🧪 Testing

### 1. Automated Unit & Integration Tests
Run the test suite using `pytest`:
```bash
python -m pytest backend/tests -v
```
All 6 tests verify:
- Status calculations (`LOW`, `MEDIUM`, `FULL`, `DANGER`)
- 80% danger threshold enforcement
- Reading creation, retrieval, and deletion
- Aggregate statistics and history queries
- Dynamic Hotspot IP updates
- Real-time WebSocket connection and initial state payload

### 2. Testing Without Hardware (Hardware Simulator)
Use `backend/simulator.py` to test the dashboard, alarm sounds, and database logging when your ESP32 is offline:

**Option A: Push Test Cycle**
Simulates fill level ramping from 20% to 92% (triggering the 80% Danger alarm):
```bash
python backend/simulator.py --mode push
```

**Option B: Mock ESP32 Web Server**
Runs an HTTP server on port 8080 mimicking the exact ESP32 `/data` endpoint:
```bash
python backend/simulator.py --mode server --port 8080
```
Then set your ESP32 target IP to `localhost` and port `8080` in the dashboard or `.env`.

> ⚠️ **Hardware Verification Note**: Simulator tests verify backend and dashboard functionality. Physical hardware integration requires powering your actual ESP32 connected to the same local WiFi or mobile hotspot as your PC.

---

## 📖 API Documentation & Swagger

When the backend is running, interactive API documentation is available at:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Key Endpoints:
- `GET /`: Responsive Web Dashboard
- `GET /api/readings/latest`: Latest sensor reading and ESP32 online status
- `GET /api/readings`: Historical sensor readings (with pagination)
- `GET /api/readings/history`: Recent readings formatted for time-series charts
- `POST /api/readings`: Record a sensor reading (manual or simulator)
- `GET /api/stats`: Aggregate status counts and current bin metrics
- `GET /api/config`: Current poller configuration and target URL
- `POST /api/config/esp32-ip`: Update ESP32 IP dynamically for mobile hotspots
- `DELETE /api/readings`: Clear sensor reading history
- `WS /ws`: Real-time WebSocket connection for instant UI updates

