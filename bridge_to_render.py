"""
Render Cloud Gateway / Bridge for ESP32
Polls your ESP32 on your local WiFi/Hotspot (without modifying your Arduino sketch!)
and forwards the readings to your live Render cloud backend.
"""

import time
import requests
import argparse
from dotenv import load_dotenv
import os

load_dotenv()

def run_bridge(esp32_ip="192.168.1.100", render_url=None, poll_interval=2.0):
    if not render_url:
        print("[ERROR] Please provide your Render URL with --render-url (e.g. https://smartbin.onrender.com)")
        return

    render_api = f"{render_url.rstrip('/')}/api/readings"
    esp32_endpoint = f"http://{esp32_ip.strip()}/data" if not esp32_ip.startswith("http") else f"{esp32_ip.rstrip('/')}/data"

    print(f"🚀 Starting SmartBin Cloud Bridge...")
    print(f"   📡 Local ESP32: {esp32_endpoint}")
    print(f"   ☁️ Render Cloud API: {render_api}")
    print(f"   ⏱️ Poll Interval: {poll_interval}s\n")

    consecutive_errors = 0
    while True:
        try:
            # 1. Fetch from local ESP32
            res = requests.get(esp32_endpoint, timeout=3.0)
            if res.status_code == 200:
                data = res.json()
                is_valid = bool(data.get("valid", False))
                distance = float(data.get("distance", -1.0))
                fill = int(data.get("fill", 0))

                # 2. Forward to Render
                payload = {
                    "distance_cm": distance,
                    "fill_percentage": fill,
                    "is_valid": is_valid,
                    "source": "ESP32_BRIDGE"
                }
                render_res = requests.post(render_api, json=payload, timeout=5.0)
                if render_res.status_code == 200:
                    status = render_res.json().get("status", "OK")
                    print(f"[{time.strftime('%X')}] Forwarded reading: {fill}% ({distance:.1f} cm) | Status: {status}")
                    consecutive_errors = 0
                else:
                    print(f"[{time.strftime('%X')}] Render returned status: {render_res.status_code}")
            else:
                print(f"[{time.strftime('%X')}] ESP32 returned status: {res.status_code}")
        except requests.exceptions.ConnectionError:
            consecutive_errors += 1
            if consecutive_errors % 5 == 1:
                print(f"[{time.strftime('%X')}] Waiting for ESP32 at {esp32_endpoint}... (Check WiFi/Hotspot)")
        except Exception as e:
            print(f"[{time.strftime('%X')}] Bridge error: {e}")

        time.sleep(poll_interval)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Forward ESP32 readings to Render cloud")
    parser.add_argument("--esp32", default=os.getenv("ESP32_IP", "192.168.1.100"), help="ESP32 IP address")
    parser.add_argument("--render-url", help="Your Render app URL (e.g. https://smartbin-app.onrender.com)")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds")
    args = parser.parse_args()

    run_bridge(esp32_ip=args.esp32, render_url=args.render_url, poll_interval=args.interval)

