/* StretchSense session UI logic.
   Frontend only: consumes existing FastAPI status/control endpoints. */
(function () {
  "use strict";

  const debugEnabled = document.body.dataset.debug === "1";
  const el = (id) => document.getElementById(id);

  const els = {
    cameraBadge: el("cam-source-badge"),
    cameraText: el("cam-source-text"),
    statePill: el("state-pill"),
    stateText: el("state-text"),
    timer: el("timer"),
    stretchStep: el("stretch-step"),
    stretchName: el("stretch-name"),
    instruction: el("instruction"),
    progressBar: el("progress-bar"),
    progressBarSide: el("progress-bar-side"),
    progressPct: el("progress-pct"),
    scoreValue: el("score-value"),
    scoreLabel: el("score-label"),
    stabilityBar: el("stability-bar"),
    stabilityPct: el("stability-pct"),
    metaMode: el("meta-mode"),
    metaFocus: el("meta-focus"),
    metaDuration: el("meta-duration"),
    phonePairing: el("phonePairing"),
    debugPanel: el("debug-panel"),
  };

  function setText(id, value) {
    const node = el(id);
    if (node) node.textContent = value;
  }

  function cameraKind(camera) {
    if (!camera) return "none";
    if (camera.selected_camera_source === "USB_CAMERA" && camera.usb_camera_detected) return "usb";
    if (camera.selected_camera_source === "PHONE_QR" && camera.phone_connected) return "phone";
    if (camera.selected_camera_source === "PHONE_QR") return "waiting";
    return "none";
  }

  function cameraLabel(kind) {
    return {
      usb: "USB Camera",
      phone: "Phone Camera",
      waiting: "Waiting for Phone",
      none: "No Camera",
    }[kind] || "No Camera";
  }

  function setCamera(camera) {
    const kind = cameraKind(camera);
    if (els.cameraBadge) {
      els.cameraBadge.className = "badge";
      els.cameraBadge.classList.add(kind === "usb" ? "ok" : kind === "phone" ? "info" : kind === "waiting" ? "warn" : "bad");
    }
    if (els.cameraText) els.cameraText.textContent = cameraLabel(kind);
    if (els.phonePairing) els.phonePairing.classList.toggle("visible", kind === "waiting" || kind === "none");

    if (debugEnabled) {
      setText("d-cam-source", camera.selected_camera_source || kind);
      setText("d-usb", String(Boolean(camera.usb_camera_detected)));
      setText("d-phone", String(Boolean(camera.phone_connected)));
      setText("d-fps", Number(camera.fps || 0).toFixed(1));
      setText("d-size", camera.frame_width && camera.frame_height ? `${camera.frame_width}x${camera.frame_height}` : "--");
      setText("d-frame-ts", camera.last_frame_timestamp || "--");
      setText("d-forced", camera.force_camera_mode || "--");
    }
  }

  function normalizedState(state) {
    return String(state || "IDLE").replaceAll("_", " ");
  }

  function formatTime(seconds) {
    const safe = Math.max(0, Number(seconds || 0));
    const minutes = Math.floor(safe / 60).toString().padStart(2, "0");
    const rest = Math.floor(safe % 60).toString().padStart(2, "0");
    return `${minutes}:${rest}`;
  }

  function shortInstruction(instruction) {
    const map = {
      "Get ready": "Get ready",
      "Hold the stretch": "Hold the stretch",
      "Good, keep steady": "Good, keep steady",
      "Stretch complete": "Done",
      "Press Start": "Press Start",
      "No camera": "No Camera",
      "Scan QR": "Scan QR",
    };
    return map[instruction] || instruction || "Press Start";
  }

  function scoreLabel(score) {
    if (score >= 85) return "Good";
    if (score >= 50) return "Steady";
    if (score > 0) return "Adjust";
    return "Placeholder";
  }

  function setSession(session) {
    if (!session) return;
    const state = normalizedState(session.state);
    if (els.statePill) els.statePill.dataset.state = state;
    if (els.stateText) els.stateText.textContent = state;
    if (els.timer) {
      els.timer.textContent = formatTime(session.remaining_time);
      els.timer.classList.toggle("hold", session.state === "HOLD");
    }
    if (els.stretchName) els.stretchName.textContent = session.current_stretch || "Stretch";
    if (els.instruction) els.instruction.textContent = shortInstruction(session.instruction);
    if (els.stretchStep) {
      const total = Array.isArray(session.routine) ? session.routine.length : 3;
      const step = Number(session.current_index || 0) + 1;
      els.stretchStep.textContent = `Stretch ${step} of ${total}`;
    }
    if (els.metaMode) els.metaMode.textContent = session.mode_label || session.mode || "--";
    if (els.metaFocus) els.metaFocus.textContent = session.body_focus_label || session.body_focus || "--";
    if (els.metaDuration) els.metaDuration.textContent = `${session.duration || "--"} min`;

    const score = Number(session.score || 0);
    if (els.scoreValue) els.scoreValue.textContent = String(score);
    if (els.scoreLabel) els.scoreLabel.textContent = scoreLabel(score);

    const elapsed = Number(session.elapsed_time || 0);
    const progress = Math.max(0, Math.min(1, elapsed / 20));
    const progressPct = Math.round(progress * 100);
    const stabilityPct = Math.max(0, Math.min(100, score));
    if (els.progressBar) els.progressBar.style.width = `${progressPct}%`;
    if (els.progressBarSide) els.progressBarSide.style.width = `${progressPct}%`;
    if (els.progressPct) els.progressPct.textContent = `${progressPct}%`;
    if (els.stabilityBar) els.stabilityBar.style.width = `${stabilityPct}%`;
    if (els.stabilityPct) els.stabilityPct.textContent = `${stabilityPct}%`;

    if (debugEnabled) {
      setText("d-state", state);
      setText("d-elapsed", `${elapsed.toFixed(1)}s`);
      setText("d-mode", session.mode || "--");
      setText("d-focus", session.body_focus || "--");
      setText("d-duration", String(session.duration || "--"));
    }
  }

  async function refreshStatus() {
    try {
      const response = await fetch("/api/status", { cache: "no-store" });
      if (!response.ok) return;
      const status = await response.json();
      setCamera(status.camera || {});
      setSession(status.session || {});
      if (debugEnabled) {
        setText("d-url", status.qr_url || status.local_ip_or_base_url || "--");
        setText("debug-time", new Date().toLocaleTimeString());
      }
    } catch (error) {
      console.error(error);
    }
  }

  document.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const action = button.dataset.action;
      try {
        const response = await fetch(`/api/session/${action}`, { method: "POST" });
        if (!response.ok) throw new Error(`Action failed: ${action}`);
        await refreshStatus();
      } catch (error) {
        console.error(error);
      }
    });
  });

  if (debugEnabled && els.debugPanel) {
    els.debugPanel.classList.add("visible");
  }

  refreshStatus();
  window.setInterval(refreshStatus, 1000);
})();
