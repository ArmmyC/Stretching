const debugEnabled = document.body.dataset.debug === "1";
const els = {
  cameraBadge: document.getElementById("cameraBadge"),
  modeLabel: document.getElementById("modeLabel"),
  focusLabel: document.getElementById("focusLabel"),
  timer: document.getElementById("timer"),
  instruction: document.getElementById("instruction"),
  stretchName: document.getElementById("stretchName"),
  stateLabel: document.getElementById("stateLabel"),
  scoreValue: document.getElementById("scoreValue"),
  phonePairing: document.getElementById("phonePairing"),
  debugToggle: document.getElementById("debugToggle"),
  debugPanel: document.getElementById("debugPanel"),
  debugJson: document.getElementById("debugJson"),
};

async function postAction(action) {
  const response = await fetch(`/api/session/${action}`, { method: "POST" });
  if (!response.ok) {
    throw new Error(`Action failed: ${action}`);
  }
  await refreshStatus();
}

async function refreshStatus() {
  const response = await fetch("/api/status", { cache: "no-store" });
  if (!response.ok) {
    return;
  }
  const status = await response.json();
  const camera = status.camera;
  const session = status.session;

  els.cameraBadge.textContent = camera.source_label;
  els.modeLabel.textContent = session.mode_label;
  els.focusLabel.textContent = session.body_focus_label;
  els.timer.textContent = String(session.remaining_time).padStart(2, "0");
  els.instruction.textContent = shortInstruction(session.instruction);
  els.stretchName.textContent = session.current_stretch;
  els.stateLabel.textContent = session.state;
  els.scoreValue.textContent = session.score;

  const showPairing = camera.selected_camera_source !== "USB_CAMERA" && !camera.phone_connected;
  els.phonePairing.classList.toggle("hidden", !showPairing);

  if (debugEnabled || !els.debugPanel.classList.contains("hidden")) {
    els.debugJson.textContent = JSON.stringify({
      selected_camera_source: camera.selected_camera_source,
      usb_camera_detected: camera.usb_camera_detected,
      phone_connected: camera.phone_connected,
      fps: camera.fps,
      frame_width: camera.frame_width,
      frame_height: camera.frame_height,
      last_frame_timestamp: camera.last_frame_timestamp,
      session_state: session.state,
      session_elapsed_time: session.elapsed_time,
      selected_mode: session.mode,
      selected_body_focus: session.body_focus,
      selected_duration: session.duration,
      force_camera_mode: camera.force_camera_mode,
      local_ip_or_qr_url: status.qr_url,
    }, null, 2);
  }
}

function shortInstruction(instruction) {
  const map = {
    "Get ready": "Get ready",
    "Hold the stretch": "Hold",
    "Good, keep steady": "Good",
    "Stretch complete": "Done",
    "Press Start": "Press Start",
    "No camera": "No Camera",
    "Scan QR": "Scan QR",
  };
  return map[instruction] || instruction;
}

document.querySelectorAll("[data-action]").forEach((button) => {
  button.addEventListener("click", async () => {
    try {
      await postAction(button.dataset.action);
    } catch (error) {
      console.error(error);
    }
  });
});

els.debugToggle.addEventListener("click", () => {
  els.debugPanel.classList.toggle("hidden");
  refreshStatus();
});

refreshStatus();
window.setInterval(refreshStatus, 1000);
