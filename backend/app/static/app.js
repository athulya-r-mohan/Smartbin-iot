// SmartBin Frontend Application Logic
let ws = null;
let audioContext = null;
let soundEnabled = false;
let isMuted = false;
let previousDanger = false;
let lastAlarmTime = 0;
let historyChart = null;

// Initialize on load
document.addEventListener("DOMContentLoaded", () => {
  initChart();
  fetchInitialConfig();
  fetchHistory();
  initWebSocket();
});

// ================= AUDIO CONTEXT SYNTHESIZER =================
function toggleSound() {
  try {
    if (!audioContext) {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioContext.state === "suspended") {
      audioContext.resume();
    }
    soundEnabled = !soundEnabled;
    const btn = document.getElementById("soundToggleBtn");
    if (soundEnabled) {
      btn.textContent = "🔊 Sound Alerts Active";
      btn.classList.add("active");
      playTestBeep();
    } else {
      btn.textContent = "🔔 Enable Sound Alerts";
      btn.classList.remove("active");
    }
  } catch (e) {
    alert("Audio initialization failed. Check browser permissions.");
  }
}

function playTestBeep() {
  if (!audioContext) return;
  const osc = audioContext.createOscillator();
  const gain = audioContext.createGain();
  osc.connect(gain);
  gain.connect(audioContext.destination);
  osc.type = "sine";
  osc.frequency.setValueAtTime(659.25, audioContext.currentTime); // E5
  gain.gain.setValueAtTime(0.2, audioContext.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, audioContext.currentTime + 0.3);
  osc.start();
  osc.stop(audioContext.currentTime + 0.35);
}

function playDangerAlarm() {
  if (!soundEnabled || isMuted || !audioContext) return;

  const now = Date.now();
  if (now - lastAlarmTime < 8000) return; // Cooldown between alarm bursts
  lastAlarmTime = now;

  // 3-pulse urgent buzzer alarm (880Hz -> 659Hz alternating)
  for (let i = 0; i < 3; i++) {
    const osc = audioContext.createOscillator();
    const gain = audioContext.createGain();
    osc.connect(gain);
    gain.connect(audioContext.destination);

    osc.type = "sawtooth";
    osc.frequency.setValueAtTime(880, audioContext.currentTime + i * 0.4);
    osc.frequency.setValueAtTime(659, audioContext.currentTime + i * 0.4 + 0.15);

    const start = audioContext.currentTime + i * 0.4;
    gain.gain.setValueAtTime(0.001, start);
    gain.gain.linearRampToValueAtTime(0.3, start + 0.05);
    gain.gain.setValueAtTime(0.3, start + 0.25);
    gain.gain.linearRampToValueAtTime(0.001, start + 0.35);

    osc.start(start);
    osc.stop(start + 0.36);
  }
}

function dismissDangerAlert() {
  isMuted = true;
  document.getElementById("dangerBanner").classList.add("hidden");
  setTimeout(() => { isMuted = false; }, 30000); // Unmute after 30 seconds
}

// ================= WEBSOCKET & DATA UPDATES =================
function initWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws`;

  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    updateBackendStatus(true);
  };

  ws.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      if (payload.type === "new_reading" || payload.type === "initial_state") {
        applyReading(payload.data);
      }
    } catch (e) {
      console.error("Failed to parse websocket message:", e);
    }
  };

  ws.onclose = () => {
    updateBackendStatus(false);
    // Reconnect after 3 seconds
    setTimeout(initWebSocket, 3000);
  };

  ws.onerror = () => {
    updateBackendStatus(false);
  };
}

function updateBackendStatus(connected) {
  const badge = document.getElementById("backendBadge");
  const text = document.getElementById("backendStatusText");
  const dot = badge.querySelector(".dot");

  if (connected) {
    dot.className = "dot connected";
    text.textContent = "Connected";
  } else {
    dot.className = "dot offline";
    text.textContent = "Disconnected";
  }
}

function updateESP32Status(online) {
  const badge = document.getElementById("esp32Badge");
  const text = document.getElementById("esp32StatusText");
  const dot = badge.querySelector(".dot");

  if (online) {
    dot.className = "dot connected";
    text.textContent = "Online";
  } else {
    dot.className = "dot offline";
    text.textContent = "Offline / Waiting";
  }
}

// Apply reading to UI elements
function applyReading(reading) {
  if (!reading) return;

  const fill = reading.fill_percentage;
  const distance = reading.distance_cm;
  const status = (reading.status || "LOW").toUpperCase();
  const isValid = reading.is_valid !== false;

  updateESP32Status(reading.esp32_online);

  // Numbers & Text
  document.getElementById("percentageVal").textContent = isValid ? fill : "--";
  document.getElementById("distanceVal").textContent = isValid ? `${distance.toFixed(1)} cm` : "No reading";
  document.getElementById("statusVal").textContent = status;
  document.getElementById("sensorValidVal").textContent = isValid ? "Normal" : "Error / Blocked";
  
  if (reading.timestamp) {
    const timeStr = new Date(reading.timestamp).toLocaleTimeString();
    document.getElementById("lastUpdatedVal").textContent = timeStr;
  }

  // Visual Bin Fill Level & Color
  const binFill = document.getElementById("binFill");
  const progressBarFill = document.getElementById("progressBarFill");
  const statusPill = document.getElementById("statusPill");

  const cappedFill = Math.min(Math.max(fill, 0), 100);
  binFill.style.height = `${cappedFill}%`;
  progressBarFill.style.width = `${cappedFill}%`;

  // Status colors & classes
  statusPill.textContent = status;
  statusPill.className = `status-pill status-${status.toLowerCase()}`;

  let statusColor = "var(--status-low)";
  if (status === "DANGER") statusColor = "var(--status-danger)";
  else if (status === "FULL") statusColor = "var(--status-full)";
  else if (status === "MEDIUM") statusColor = "var(--status-medium)";

  binFill.style.backgroundColor = statusColor;
  progressBarFill.style.backgroundColor = statusColor;

  // Active chip in threshold list
  highlightActiveChip(status);

  // Danger Banner and Alarm logic
  const dangerBanner = document.getElementById("dangerBanner");
  if (status === "DANGER" && isValid) {
    if (!isMuted) {
      dangerBanner.classList.remove("hidden");
    }
    playDangerAlarm();
  } else {
    dangerBanner.classList.add("hidden");
  }

  // Append point to Chart
  if (historyChart && reading.timestamp && isValid) {
    appendChartData(new Date(reading.timestamp).toLocaleTimeString(), fill);
  }
}

function highlightActiveChip(status) {
  const chips = {
    LOW: document.getElementById("chipLow"),
    MEDIUM: document.getElementById("chipMedium"),
    FULL: document.getElementById("chipFull"),
    DANGER: document.getElementById("chipDanger")
  };

  Object.keys(chips).forEach(key => {
    if (key === status) {
      chips[key]?.classList.add("active");
    } else {
      chips[key]?.classList.remove("active");
    }
  });
}

// ================= CHART CONFIGURATION =================
function initChart() {
  const ctx = document.getElementById("historyChart").getContext("2d");
  historyChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Bin Fill (%)",
          data: [],
          borderColor: "#059669",
          backgroundColor: "rgba(5, 150, 105, 0.1)",
          borderWidth: 2.5,
          tension: 0.3,
          fill: true,
          pointRadius: 3,
          pointHoverRadius: 6,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          min: 0,
          max: 100,
          ticks: {
            stepSize: 20,
            callback: (v) => `${v}%`
          },
          grid: {
            color: "#e2e8f0"
          }
        },
        x: {
          grid: {
            display: false
          }
        }
      },
      plugins: {
        legend: {
          display: false
        },
        tooltip: {
          callbacks: {
            label: (ctx) => `Fill: ${ctx.parsed.y}%`
          }
        }
      }
    }
  });
}

function appendChartData(timeLabel, fillValue) {
  if (!historyChart) return;
  const labels = historyChart.data.labels;
  const data = historyChart.data.datasets[0].data;

  // Don't add duplicate if timestamp matches the last entry
  if (labels.length > 0 && labels[labels.length - 1] === timeLabel) return;

  labels.push(timeLabel);
  data.push(fillValue);

  if (labels.length > 25) {
    labels.shift();
    data.shift();
  }

  // Dynamic line color if latest is danger
  if (fillValue >= 80) {
    historyChart.data.datasets[0].borderColor = "#ef4444";
    historyChart.data.datasets[0].backgroundColor = "rgba(239, 68, 68, 0.15)";
  } else if (fillValue >= 75) {
    historyChart.data.datasets[0].borderColor = "#f97316";
    historyChart.data.datasets[0].backgroundColor = "rgba(249, 115, 22, 0.15)";
  } else if (fillValue >= 50) {
    historyChart.data.datasets[0].borderColor = "#f59e0b";
    historyChart.data.datasets[0].backgroundColor = "rgba(245, 158, 11, 0.15)";
  } else {
    historyChart.data.datasets[0].borderColor = "#059669";
    historyChart.data.datasets[0].backgroundColor = "rgba(5, 150, 105, 0.1)";
  }

  historyChart.update();
}

async function fetchHistory() {
  try {
    const res = await fetch("/api/readings/history?limit=25");
    if (res.ok) {
      const data = await res.json();
      if (historyChart && Array.isArray(data)) {
        historyChart.data.labels = data.map(d => new Date(d.timestamp).toLocaleTimeString());
        historyChart.data.datasets[0].data = data.map(d => d.fill_percentage);
        historyChart.update();
      }
    }
  } catch (e) {
    console.error("Could not fetch reading history:", e);
  }
}

// ================= CONFIG & HOTSPOT SUPPORT =================
async function fetchInitialConfig() {
  try {
    const res = await fetch("/api/config");
    if (res.ok) {
      const cfg = await res.json();
      document.getElementById("targetIpInput").value = cfg.esp32_ip;
      document.getElementById("currentTargetUrl").textContent = cfg.target_url;
    }
  } catch (e) {
    console.error("Could not fetch config:", e);
  }
}

async function updateTargetIp() {
  const ip = document.getElementById("targetIpInput").value.trim();
  if (!ip) {
    alert("Please enter a valid IP address or hostname");
    return;
  }
  try {
    const res = await fetch("/api/config/esp32-ip", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ esp32_ip: ip })
    });
    if (res.ok) {
      const updated = await res.json();
      document.getElementById("currentTargetUrl").textContent = updated.target_url;
      alert(`ESP32 Target URL updated to: ${updated.target_url}`);
    }
  } catch (e) {
    alert("Failed to update target IP: " + e.message);
  }
}

// Test reading simulator button for convenience
async function simulateTestReading() {
  const randomPercent = Math.floor(Math.random() * 60) + 30; // 30% to 90%
  const distance = (18.8 - (randomPercent / 100) * (18.8 - 2.6)).toFixed(1);
  try {
    await fetch("/api/readings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        distance_cm: parseFloat(distance),
        fill_percentage: randomPercent,
        is_valid: true,
        source: "SIMULATOR"
      })
    });
  } catch (e) {
    alert("Test reading failed: " + e.message);
  }
}

