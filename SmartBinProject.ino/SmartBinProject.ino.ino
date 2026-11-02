#include <WiFi.h>
#include <WebServer.h>
#include <math.h>

// ========== WIFI SETTINGS ==========
const char* ssid = "Makkappathalil";
const char* password = "at123456";

// ========== SENSOR PINS ==========
#define TRIG_PIN 5
#define ECHO_PIN 18

// ========== CALIBRATION ==========
const float EMPTY_DISTANCE_CM = 18.8;
const float FULL_DISTANCE_CM = 2.6;

const int DANGER_THRESHOLD = 80;

// ========== WEB SERVER ==========
WebServer server(80);

// ========== SENSOR VARIABLES ==========
float distanceCm = -1.0;
int fillPercentage = 0;
bool sensorValid = false;

unsigned long lastSensorRead = 0;
const unsigned long SENSOR_INTERVAL = 500;

// ========== READ SENSOR ==========
float readDistance() {
  const int samples = 5;
  float readings[samples];
  int validCount = 0;

  for (int i = 0; i < samples; i++) {
    digitalWrite(TRIG_PIN, LOW);
    delayMicroseconds(3);

    digitalWrite(TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);

    unsigned long duration = pulseIn(ECHO_PIN, HIGH, 30000);

    if (duration > 0) {
      float cm = duration * 0.0343f / 2.0f;

      if (cm >= 2.0f && cm <= 400.0f) {
        readings[validCount++] = cm;
      }
    }

    delay(30);
  }

  if (validCount == 0) {
    return -1.0f;
  }

  // Sort readings
  for (int i = 0; i < validCount - 1; i++) {
    for (int j = i + 1; j < validCount; j++) {
      if (readings[i] > readings[j]) {
        float temp = readings[i];
        readings[i] = readings[j];
        readings[j] = temp;
      }
    }
  }

  // Median reading
  if (validCount % 2 == 1) {
    return readings[validCount / 2];
  }

  return (readings[validCount / 2 - 1] +
          readings[validCount / 2]) / 2.0f;
}

// ========== CALCULATE FILL ==========
int calculateFillPercentage(float distance) {
  float percentage =
      ((EMPTY_DISTANCE_CM - distance) /
       (EMPTY_DISTANCE_CM - FULL_DISTANCE_CM)) * 100.0f;

  percentage = constrain(percentage, 0.0f, 100.0f);

  return (int)round(percentage);
}

// ========== DASHBOARD HTML ==========
// IMPORTANT: Keep the opening and closing HTML markers unchanged.
const char dashboardHTML[] PROGMEM = R"HTML(
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Smart Waste Bin</title>

<style>
* {
  box-sizing: border-box;
}

body {
  margin: 0;
  padding: 20px;
  font-family: Arial, sans-serif;
  background: #f0f4f8;
  color: #1e293b;
}

.container {
  max-width: 600px;
  margin: 20px auto;
}

.card {
  background: white;
  padding: 30px;
  border-radius: 22px;
  box-shadow: 0 5px 22px rgba(0,0,0,0.08);
}

h1 {
  text-align: center;
  margin: 15px 0 8px;
  font-size: 32px;
  color: #166b52;
}

.subtitle {
  text-align: center;
  color: #64748b;
  margin-bottom: 32px;
  font-size: 18px;
}

.label {
  color: #64748b;
  text-align: center;
  font-size: 15px;
}

.percentage {
  text-align: center;
  font-size: 68px;
  font-weight: bold;
  margin: 18px 0;
}

.progress {
  width: 100%;
  height: 20px;
  border-radius: 20px;
  overflow: hidden;
  background: #e2e8f0;
}

.progressFill {
  height: 100%;
  width: 0%;
  background: #22c55e;
  transition: width 0.4s;
}

.details {
  display: flex;
  gap: 15px;
  margin-top: 25px;
}

.box {
  flex: 1;
  min-width: 0;
  text-align: center;
  background: #f8fafc;
  border-radius: 14px;
  padding: 18px 8px;
}

.value {
  margin-top: 10px;
  font-size: 20px;
  font-weight: bold;
  overflow-wrap: anywhere;
}

.status {
  margin-top: 24px;
  padding: 17px 10px;
  border-radius: 12px;
  text-align: center;
  font-weight: bold;
  background: #dcfce7;
  color: #166534;
}

.warning {
  background: #fef3c7;
  color: #92400e;
}

.danger {
  background: #fee2e2;
  color: #b91c1c;
}

button {
  width: 100%;
  border: none;
  border-radius: 12px;
  padding: 16px;
  margin-top: 18px;
  background: #166b52;
  color: white;
  font-size: 17px;
  cursor: pointer;
}

.footer {
  text-align: center;
  margin-top: 22px;
  color: #64748b;
  font-size: 14px;
}

@media (max-width: 400px) {
  .card {
    padding: 20px;
  }

  h1 {
    font-size: 27px;
  }

  .percentage {
    font-size: 56px;
  }

  .details {
    gap: 8px;
  }

  .value {
    font-size: 17px;
  }
}
</style>
</head>

<body>
<div class="container">
<div class="card">

<h1>♻️ Smart Waste Bin</h1>
<div class="subtitle">ESP32 Live Monitoring Dashboard</div>

<div class="label">WASTE FILL LEVEL</div>
<div class="percentage" id="percentage">--%</div>

<div class="progress">
  <div class="progressFill" id="progressFill"></div>
</div>

<div class="details">
  <div class="box">
    <div class="label">Sensor Distance</div>
    <div class="value" id="distance">-- cm</div>
  </div>

  <div class="box">
    <div class="label">Bin Status</div>
    <div class="value" id="binStatus">Checking</div>
  </div>
</div>

<div class="status" id="alert">
  Connecting to sensor...
</div>

<button id="soundButton" onclick="enableSound()">
  Enable Sound Alerts
</button>

<div class="footer" id="updated">
  ESP32 Smart Bin Monitoring System
</div>

</div>
</div>

<script>
let soundEnabled = false;
let audioContext = null;
let previousDanger = false;
let lastAlarmTime = 0;

// Enable audio after user clicks the button
async function enableSound() {
  try {
    if (!audioContext) {
      audioContext = new (
        window.AudioContext || window.webkitAudioContext
      )();
    }

    if (audioContext.state === "suspended") {
      await audioContext.resume();
    }

    soundEnabled = true;

    document.getElementById("soundButton").textContent =
      "Sound Alerts Enabled";

    document.getElementById("soundButton").style.background =
      "#16a34a";

    // Test sound
    playAlarm();

  } catch (error) {
    alert("Could not enable sound. Check browser settings.");
  }
}

// Three long beeps
function playAlarm() {
  if (!soundEnabled || !audioContext) {
    return;
  }

  for (let i = 0; i < 3; i++) {
    const oscillator = audioContext.createOscillator();
    const gain = audioContext.createGain();

    oscillator.connect(gain);
    gain.connect(audioContext.destination);

    oscillator.type = "sine";
    oscillator.frequency.value = 880;

    const startTime = audioContext.currentTime + i * 0.9;

    gain.gain.setValueAtTime(0.001, startTime);

    gain.gain.linearRampToValueAtTime(
      0.3, startTime + 0.1
    );

    gain.gain.setValueAtTime(
      0.3, startTime + 0.65
    );

    gain.gain.linearRampToValueAtTime(
      0.001, startTime + 0.8
    );

    oscillator.start(startTime);
    oscillator.stop(startTime + 0.85);
  }
}

// Update dashboard
async function updateDashboard() {
  try {
    const response = await fetch("/data", {
      cache: "no-store"
    });

    if (!response.ok) {
      throw new Error("HTTP error");
    }

    const data = await response.json();

    if (!data.valid) {
      document.getElementById("percentage").textContent = "--%";
      document.getElementById("distance").textContent = "No reading";
      document.getElementById("binStatus").textContent = "Sensor error";

      const alertBox = document.getElementById("alert");

      alertBox.textContent = "Check sensor connection";
      alertBox.className = "status danger";

      previousDanger = false;
      return;
    }

    const percentage = data.fill;
    const danger = percentage >= 80;

    document.getElementById("percentage").textContent =
      percentage + "%";

    document.getElementById("distance").textContent =
      data.distance.toFixed(1) + " cm";

    document.getElementById("progressFill").style.width =
      percentage + "%";

    const fill = document.getElementById("progressFill");
    const alertBox = document.getElementById("alert");

    if (danger) {
      fill.style.background = "#ef4444";

      alertBox.textContent = "DANGER: BIN IS ALMOST FULL";
      alertBox.className = "status danger";

      document.getElementById("binStatus").textContent = "DANGER";

      const now = Date.now();

      // Alarm on entering danger, then repeat every 10 seconds
      if (!previousDanger || now - lastAlarmTime >= 10000) {
        playAlarm();
        lastAlarmTime = now;
      }

    } else if (percentage >= 50) {
      fill.style.background = "#f59e0b";

      alertBox.textContent = "WARNING: BIN IS FILLING UP";
      alertBox.className = "status warning";

      document.getElementById("binStatus").textContent = "FILLING";

    } else {
      fill.style.background = "#22c55e";

      alertBox.textContent = "Bin level is normal";
      alertBox.className = "status";

      document.getElementById("binStatus").textContent = "NORMAL";
    }

    previousDanger = danger;

    document.getElementById("updated").textContent =
      "Last updated: " + new Date().toLocaleTimeString();

  } catch (error) {
    const alertBox = document.getElementById("alert");

    alertBox.textContent = "Dashboard connection lost";
    alertBox.className = "status danger";
  }
}

updateDashboard();
setInterval(updateDashboard, 1000);
</script>

</body>
</html>
)HTML";

// ========== DATA API ==========
void handleData() {
  String json = "{";

  json += "\"valid\":";
  json += (sensorValid ? "true" : "false");

  json += ",\"distance\":";
  json += String(sensorValid ? distanceCm : -1.0f, 1);

  json += ",\"fill\":";
  json += String(sensorValid ? fillPercentage : 0);

  json += ",\"danger\":";
  json += (sensorValid && fillPercentage >= DANGER_THRESHOLD)
          ? "true" : "false";

  json += "}";

  server.sendHeader("Cache-Control", "no-store");
  server.send(200, "application/json", json);
}

// ========== HOME PAGE ==========
void handleHome() {
  server.send_P(200, "text/html", dashboardHTML);
}

// ========== SETUP ==========
void setup() {
  Serial.begin(115200);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  digitalWrite(TRIG_PIN, LOW);

  Serial.println();
  Serial.println("Connecting to Wi-Fi...");

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  unsigned long startAttempt = millis();

  while (WiFi.status() != WL_CONNECTED &&
         millis() - startAttempt < 30000) {
    delay(500);
    Serial.print(".");
  }

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println();
    Serial.println("Wi-Fi connection failed!");
    Serial.println("Check Wi-Fi name and password.");
    return;
  }

  Serial.println();
  Serial.println("Wi-Fi connected!");

  Serial.print("ESP32 IP address: ");
  Serial.println(WiFi.localIP());

  server.on("/", HTTP_GET, handleHome);
  server.on("/data", HTTP_GET, handleData);

  server.begin();

  Serial.println("Web server started!");
}

// ========== MAIN LOOP ==========
void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    delay(100);
    return;
  }

  server.handleClient();

  if (millis() - lastSensorRead >= SENSOR_INTERVAL) {
    lastSensorRead = millis();

    float newDistance = readDistance();

    if (newDistance >= 0) {
      distanceCm = newDistance;

      fillPercentage = calculateFillPercentage(distanceCm);
      sensorValid = true;

      Serial.print("Distance: ");
      Serial.print(distanceCm, 1);

      Serial.print(" cm | Fill: ");
      Serial.print(fillPercentage);

      Serial.println("%");

    } else {
      sensorValid = false;

      Serial.println("Sensor error: No valid distance reading");
    }
  }

  delay(2);
}