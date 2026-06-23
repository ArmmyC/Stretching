const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";
const WS_BASE = API_BASE.replace(/^http/, "ws");

async function jsonRequest(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

export function createSession() {
  return jsonRequest(`${API_BASE}/api/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
}

export function scoreSession(sessionId, signal) {
  return jsonRequest(`${API_BASE}/api/sessions/${sessionId}/score`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(signal),
  });
}

export function advanceSession(sessionId) {
  return jsonRequest(`${API_BASE}/api/sessions/${sessionId}/advance`, {
    method: "POST",
  });
}

export function loadDailyQuests() {
  return jsonRequest(`${API_BASE}/api/quests/daily`);
}

export function openPoseSocket(onResult) {
  const socket = new WebSocket(`${WS_BASE}/ws/pose-stream`);
  socket.addEventListener("message", (event) => onResult(JSON.parse(event.data)));
  return socket;
}
