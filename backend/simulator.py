"""
ESP32 Smart Bin Hardware Simulator
Use this script to test the full system (FastAPI, PostgreSQL, Dashboard, Audio Alert)
without needing the physical ESP32 powered on.

Options:
1. Mode 'push': Directly posts simulated sensor readings to the FastAPI backend.
2. Mode 'server': Runs a mock ESP32 HTTP server on port 8080 serving the exact `/data` endpoint
                 matching your ESP32 Arduino code!
"""

import sys
import time
import math
import argparse
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

EMPTY_DISTANCE_CM = 18.8
FULL_DISTANCE_CM = 2.6

# State for mock server
simulated_state = {
    "fill": 15,
    "distance": 16.4,
    "valid": True,
    "danger": False
}

class MockESP32Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/data":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            payload = json.dumps(simulated_state)
            self.wfile.write(payload.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Quiet mock logging
        pass

def run_mock_server(port=8080):
    print(f"[SIMULATOR] Starting Mock ESP32 Web Server on http://localhost:{port}/data")
    print(f"[SIMULATOR] Set your backend ESP32_IP=localhost and ESP32_PORT={port} or update via Dashboard!")
    server = HTTPServer(("0.0.0.0", port), MockESP32Handler)

    # Background thread to animate fill percentage
    import threading
    def animate():
        angle = 0
        while True:
            # Sine wave oscillation between 10% and 95%
            sine_val = (math.sin(angle) + 1.0) / 2.0  # 0.0 to 1.0
            fill = int(10 + sine_val * 85)
            distance = round(EMPTY_DISTANCE_CM - (fill / 100.0) * (EMPTY_DISTANCE_CM - FULL_DISTANCE_CM), 1)
            simulated_state["fill"] = fill
            simulated_state["distance"] = distance
            simulated_state["danger"] = fill >= 80
            print(f"[SIMULATOR STATE] Fill: {fill}% | Distance: {distance} cm | Danger: {simulated_state['danger']}")
            angle += 0.2
            time.sleep(2.0)

    t = threading.Thread(target=animate, daemon=True)
    t.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[SIMULATOR] Stopped.")

def run_push_mode(backend_url="http://localhost:8000"):
    print(f"[SIMULATOR] Pushing simulated readings to {backend_url}/api/readings")
    print("[SIMULATOR] Ramping up fill level from 20% to 90% to trigger 80% Danger Alert...")
    
    fill_levels = [20, 35, 48, 55, 68, 76, 82, 88, 92, 40]
    for fill in fill_levels:
        distance = round(EMPTY_DISTANCE_CM - (fill / 100.0) * (EMPTY_DISTANCE_CM - FULL_DISTANCE_CM), 1)
        payload = {
            "distance_cm": distance,
            "fill_percentage": fill,
            "is_valid": True,
            "source": "SIMULATOR"
        }
        try:
            res = requests.post(f"{backend_url}/api/readings", json=payload, timeout=3)
            print(f"[SENT] Fill: {fill}% -> Server Response: HTTP {res.status_code} ({res.json().get('status')})")
        except Exception as e:
            print(f"[ERROR] Could not connect to backend at {backend_url}: {e}")
        time.sleep(2.0)
    print("[SIMULATOR] Push cycle completed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart Bin ESP32 Simulator")
    parser.add_argument("--mode", choices=["server", "push"], default="push",
                        help="'push' to send readings to backend; 'server' to run mock ESP32 HTTP endpoint")
    parser.add_argument("--port", type=int, default=8080, help="Port for mock server mode")
    parser.add_argument("--backend", default="http://localhost:8000", help="FastAPI backend URL")
    args = parser.parse_args()

    if args.mode == "server":
        run_mock_server(args.port)
    else:
        run_push_mode(args.backend)

