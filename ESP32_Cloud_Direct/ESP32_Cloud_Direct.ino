#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <math.h>

// ================= WIFI SETTINGS =================
// Enter your home WiFi or Mobile Hotspot credentials here:
const char* ssid = "Makkappathalil";
const char* password = "at123456";

// ================= RENDER CLOUD SETTINGS =================
// Your live Render app URL and the API Key configured in Render:
const char* serverUrl = "https://smartbin-monitor-hbms.onrender.com/api/readings";
const char* apiKey = "smartbin_secret_key_2026";

// ================= SENSOR PINS =================
#define TRIG_PIN 5
#define ECHO_PIN 18

// ================= CALIBRATION =================
const float EMPTY_DISTANCE_CM = 18.8;
const float FULL_DISTANCE_CM = 2.6;
const int DANGER_THRESHOLD = 80;

// ================= TIMING =================
unsigned long lastSendTime = 0;
const unsigned long SEND_INTERVAL_MS = 3000; // Send reading every 3 seconds

// ================= READ DISTANCE (MEDIAN FILTER) =================
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
    delay(25);
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
  return (readings[validCount / 2 - 1] + readings[validCount / 2]) / 2.0f;
}

// ================= CALCULATE FILL PERCENTAGE =================
int calculateFillPercentage(float distance) {
  float percentage = ((EMPTY_DISTANCE_CM - distance) / (EMPTY_DISTANCE_CM - FULL_DISTANCE_CM)) * 100.0f;
  percentage = constrain(percentage, 0.0f, 100.0f);
  return (int)round(percentage);
}

// ================= SEND READING TO RENDER =================
void sendReadingToCloud(float distance, int fill, bool isValid) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WIFI] Disconnected. Reconnecting...");
    WiFi.reconnect();
    return;
  }

  WiFiClientSecure client;
  client.setInsecure(); // Skip certificate verification for smooth cloud connection

  HTTPClient http;
  if (!http.begin(client, serverUrl)) {
    Serial.println("[HTTP] Unable to connect to Render host");
    return;
  }

  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", apiKey);

  // Construct JSON payload
  String jsonPayload = "{";
  jsonPayload += "\"distance_cm\":" + String(isValid ? distance : -1.0f, 1) + ",";
  jsonPayload += "\"fill_percentage\":" + String(isValid ? fill : 0) + ",";
  jsonPayload += "\"is_valid\":" + String(isValid ? "true" : "false") + ",";
  jsonPayload += "\"source\":\"ESP32_DIRECT\"";
  jsonPayload += "}";

  Serial.print("[CLOUD] Posting to Render: ");
  Serial.print(jsonPayload);

  int httpCode = http.POST(jsonPayload);

  if (httpCode > 0) {
    Serial.print(" -> Response: HTTP ");
    Serial.println(httpCode);
    if (httpCode == HTTP_CODE_OK || httpCode == 201) {
      String response = http.getString();
      Serial.print("   Payload received by Render: ");
      Serial.println(response);
    } else if (httpCode == 401) {
      Serial.println("   [ERROR 401] Invalid API Key! Check apiKey in code vs Render env.");
    }
  } else {
    Serial.print(" -> Error: ");
    Serial.println(http.errorToString(httpCode).c_str());
  }

  http.end();
}

// ================= SETUP =================
void setup() {
  Serial.begin(115200);
  delay(1000);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  digitalWrite(TRIG_PIN, LOW);

  Serial.println("\n======================================");
  Serial.println("   ESP32 SMART BIN -> RENDER CLOUD   ");
  Serial.println("======================================");
  Serial.print("Connecting to Wi-Fi: ");
  Serial.println(ssid);

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  unsigned long startAttempt = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - startAttempt < 30000) {
    delay(500);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WIFI] Connected!");
    Serial.print("[WIFI] ESP32 IP: ");
    Serial.println(WiFi.localIP());
    Serial.print("[CLOUD] Target URL: ");
    Serial.println(serverUrl);
  } else {
    Serial.println("\n[WIFI] Connection failed. Check credentials/hotspot.");
  }
}

// ================= MAIN LOOP =================
void loop() {
  unsigned long now = millis();
  if (now - lastSendTime >= SEND_INTERVAL_MS) {
    lastSendTime = now;

    float dist = readDistance();
    if (dist >= 0) {
      int fill = calculateFillPercentage(dist);
      Serial.print("\n[SENSOR] Distance: ");
      Serial.print(dist, 1);
      Serial.print(" cm | Fill: ");
      Serial.print(fill);
      Serial.println("%");

      sendReadingToCloud(dist, fill, true);
    } else {
      Serial.println("\n[SENSOR] Error: No reading from HC-SR04");
      sendReadingToCloud(-1.0f, 0, false);
    }
  }

  delay(10);
}
