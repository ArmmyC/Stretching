import { advanceSession, createSession, loadDailyQuests, openPoseSocket, scoreSession } from "./api.js";
import { frameHint, startCamera } from "./camera.js";
import { enableReminderPreview, registerServiceWorker } from "./notifications.js";
import "./styles.css";

const el = (id) => document.getElementById(id);

const state = {
  session: null,
  poseSocket: null,
  cameraStartedAt: 0,
  lastSignal: null,
};

function renderSession(session) {
  if (!session) return;
  const segment = session.segments[session.current_index];
  el("stretch-name").textContent = segment ? segment.name : "Complete";
  el("score-value").textContent = String(session.total_score || 0);
  el("xp-value").textContent = String(session.xp_earned || 0);
  const stars = segment ? segment.stars : 0;
  el("stars").textContent = "★".repeat(stars) + "☆".repeat(3 - stars);
}

async function renderQuests() {
  const quests = await loadDailyQuests();
  el("quest-list").innerHTML = quests
    .map((quest) => `<li><strong>${quest.title}</strong><span>${quest.reward_xp} XP</span></li>`)
    .join("");
}

async function handleStartCamera() {
  const video = el("camera-preview");
  await startCamera(video);
  state.cameraStartedAt = Date.now();
  el("pose-message").textContent = "Camera active";

  if (!state.poseSocket) {
    state.poseSocket = openPoseSocket(async (result) => {
      state.lastSignal = result.signal;
      el("pose-message").textContent = result.message;
      if (state.session) {
        state.session = await scoreSession(state.session.id, result.signal);
        renderSession(state.session);
      }
    });
  }

  window.setInterval(() => {
    if (!state.poseSocket || state.poseSocket.readyState !== WebSocket.OPEN) return;
    const holdSeconds = Math.max(0, (Date.now() - state.cameraStartedAt) / 1000);
    state.poseSocket.send(JSON.stringify(frameHint(video, holdSeconds)));
  }, 1000);
}

async function handleStartSession() {
  state.session = await createSession();
  renderSession(state.session);
}

async function handleAdvance() {
  if (!state.session) return;
  const payload = await advanceSession(state.session.id);
  state.session = payload.session;
  renderSession(state.session);
  if (payload.completed_quests && payload.completed_quests.length) {
    el("pose-message").textContent = `Quest complete: ${payload.completed_quests.join(", ")}`;
  }
}

async function main() {
  await registerServiceWorker();
  await renderQuests();
  el("start-camera").addEventListener("click", handleStartCamera);
  el("start-session").addEventListener("click", handleStartSession);
  el("advance-stretch").addEventListener("click", handleAdvance);
  el("enable-notifications").addEventListener("click", async () => {
    el("pose-message").textContent = await enableReminderPreview();
  });
}

main().catch((error) => {
  console.error(error);
  el("pose-message").textContent = error.message || "Something went wrong";
});
