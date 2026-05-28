/* StretchSense session UI logic.
   Frontend only: consumes existing FastAPI status/control endpoints. */
(function () {
  "use strict";

  const READY_SECONDS = 5;
  const STRETCH_SECONDS = 20;
  const debugEnabled = document.body.dataset.debug === "1";
  const el = (id) => document.getElementById(id);

  const els = {
    stage: document.querySelector(".session-stage"),
    cameraBadge: el("cam-source-badge"),
    cameraText: el("cam-source-text"),
    timer: el("timer"),
    stretchStep: el("stretch-step"),
    stretchName: el("stretch-name"),
    instruction: el("instruction"),
    progressBar: el("progress-bar"),
    scoreValue: el("score-value"),
    countdownOverlay: el("camera-countdown"),
    countdownNumber: el("countdown-number"),
    countdownLabel: el("countdown-label"),
    nextPreview: el("next-preview"),
    nextName: el("next-name"),
    nextCountdownNumber: el("next-countdown-number"),
    completeOverlay: el("session-complete"),
    completeScore: el("complete-score"),
    completeMeta: el("complete-meta"),
    debugPanel: el("debug-panel"),
  };

  let autoStartAttempted = false;
  let advanceInFlight = false;
  let previewIndex = null;
  let lastDoneIndex = null;
  let stretchScores = [];
  let lastSession = null;
  let lastHardwareFeedback = "";

  function setText(id, value) {
    const node = el(id);
    if (node) node.textContent = value;
  }

  function show(node, visible) {
    if (node) node.classList.toggle("hidden", !visible);
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
      usb: "Camera Active",
      phone: "Camera Active",
      waiting: "Waiting for Camera",
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
    return map[instruction] || instruction || "Get ready";
  }

  function readyCountdown(session) {
    const elapsed = Math.max(0, Number(session.elapsed_time || 0));
    return Math.max(1, Math.ceil(READY_SECONDS - elapsed));
  }

  function sessionTotal(session) {
    return Array.isArray(session.routine) ? session.routine.length : 1;
  }

  function sessionIndex(session) {
    return Number(session.current_index || 0);
  }

  function setStageClass(kind) {
    if (!els.stage) return;
    els.stage.classList.remove("is-countdown", "is-preview", "is-active", "is-complete");
    if (kind) els.stage.classList.add(kind);
  }

  function recordTotalScore(session) {
    const state = String(session.state || "IDLE");
    const index = sessionIndex(session);
    const score = Math.max(0, Number(session.score || 0));
    if (state === "IDLE" && index === 0) stretchScores = [];
    if (score > 0) stretchScores[index] = Math.max(stretchScores[index] || 0, score);
    return stretchScores.reduce((total, value) => total + Math.max(0, Number(value || 0)), 0);
  }

  function updateOverlays(session, totalScore) {
    const state = String(session.state || "IDLE");
    const index = sessionIndex(session);
    const total = sessionTotal(session);
    const count = readyCountdown(session);
    const isPreview = state === "READY" && previewIndex === index && index > 0;
    const isCountdown = state === "READY" && !isPreview;
    const isComplete = state === "DONE" && index >= total - 1;

    show(els.countdownOverlay, isCountdown);
    show(els.nextPreview, isPreview);
    show(els.completeOverlay, isComplete);

    if (els.countdownNumber) els.countdownNumber.textContent = String(count);
    if (els.countdownLabel) els.countdownLabel.textContent = session.current_stretch || "Get ready";
    if (els.nextName) els.nextName.textContent = session.current_stretch || "Next stretch";
    if (els.nextCountdownNumber) els.nextCountdownNumber.textContent = String(count);
    if (els.completeScore) els.completeScore.textContent = String(totalScore);
    if (els.completeMeta) {
      els.completeMeta.textContent = `${total} stretches completed`;
    }

    if (state !== "READY" && previewIndex === index) {
      previewIndex = null;
    }

    if (isComplete) {
      setStageClass("is-complete");
    } else if (isPreview) {
      setStageClass("is-preview");
    } else if (isCountdown) {
      setStageClass("is-countdown");
    } else if (state === "HOLD" || state === "GOOD") {
      setStageClass("is-active");
    } else {
      setStageClass("");
    }
  }

  function updateHud(session, totalScore) {
    const total = sessionTotal(session);
    const index = sessionIndex(session);
    const elapsed = Number(session.elapsed_time || 0);
    const state = String(session.state || "IDLE");

    if (els.timer) {
      els.timer.textContent = formatTime(session.remaining_time);
      els.timer.classList.toggle("hold", state === "HOLD" || state === "GOOD");
    }
    if (els.stretchName) els.stretchName.textContent = session.current_stretch || "Stretch";
    if (els.instruction) els.instruction.textContent = shortInstruction(session.instruction);
    if (els.stretchStep) els.stretchStep.textContent = `Stretch ${index + 1} of ${total}`;
    if (els.scoreValue) els.scoreValue.textContent = String(totalScore);

    const progress = Math.max(0, Math.min(1, elapsed / STRETCH_SECONDS));
    if (els.progressBar) els.progressBar.style.width = `${Math.round(progress * 100)}%`;

    if (debugEnabled) {
      setText("d-state", state.replaceAll("_", " "));
      setText("d-elapsed", `${elapsed.toFixed(1)}s`);
      setText("d-mode", session.mode || "--");
      setText("d-focus", session.body_focus || "--");
      setText("d-duration", String(session.duration || "--"));
    }
  }

  function sendHardwareFeedback(session, totalScore) {
    if (!window.StretchHardware) return;
    const state = String(session.state || "IDLE");
    const value = state === "READY"
      ? readyCountdown(session)
      : Math.max(0, Math.min(100, Math.round((Number(session.elapsed_time || 0) / STRETCH_SECONDS) * 100)));
    const payload = {
      page: "session",
      state,
      selection: session.current_stretch || "",
      value: state === "DONE" ? totalScore : value,
    };
    const serialized = JSON.stringify(payload);
    if (serialized === lastHardwareFeedback) return;
    lastHardwareFeedback = serialized;
    window.StretchHardware.sendFeedback(payload);
  }

  function maybeAdvance(session) {
    const state = String(session.state || "IDLE");
    const index = sessionIndex(session);
    const total = sessionTotal(session);
    if (state !== "DONE" || index >= total - 1 || advanceInFlight || lastDoneIndex === index) return;

    lastDoneIndex = index;
    advanceInFlight = true;
    postAction("next")
      .then((status) => {
        advanceInFlight = false;
        if (status && status.session) {
          previewIndex = sessionIndex(status.session);
          consumeStatus(status);
        }
      })
      .catch((error) => {
        advanceInFlight = false;
        console.error(error);
      });
  }

  function setSession(session) {
    if (!session) return;
    lastSession = session;
    const totalScore = recordTotalScore(session);
    updateHud(session, totalScore);
    updateOverlays(session, totalScore);
    sendHardwareFeedback(session, totalScore);
    maybeAdvance(session);
  }

  function consumeStatus(status) {
    setCamera(status.camera || {});
    setSession(status.session || {});
    if (debugEnabled) {
      setText("d-url", status.qr_url || status.local_ip_or_base_url || "--");
      setText("debug-time", new Date().toLocaleTimeString());
    }
  }

  async function postAction(action) {
    const response = await fetch(`/api/session/${action}`, { method: "POST" });
    if (!response.ok) throw new Error(`Action failed: ${action}`);
    const payload = await response.json();
    return payload.status || { session: payload.session || {} };
  }

  async function refreshStatus() {
    try {
      const response = await fetch("/api/status", { cache: "no-store" });
      if (!response.ok) return null;
      const status = await response.json();
      consumeStatus(status);
      return status;
    } catch (error) {
      console.error(error);
      return null;
    }
  }

  async function startIfIdle(status) {
    if (autoStartAttempted || !status || !status.session) return;
    const params = new URLSearchParams(window.location.search);
    const cameFromSetup = params.has("mode") || params.has("body_focus") || params.has("duration");
    if (status.session.state !== "IDLE" && !cameFromSetup) return;
    autoStartAttempted = true;
    try {
      if (status.session.state !== "IDLE") {
        stretchScores = [];
        await postAction("reset");
      }
      const startedStatus = await postAction("start");
      consumeStatus(startedStatus);
    } catch (error) {
      console.error(error);
    }
  }

  function setupUrl() {
    const session = lastSession || {};
    const mode = encodeURIComponent(session.mode || "before");
    const focus = encodeURIComponent(session.body_focus || "full");
    const duration = encodeURIComponent(session.duration || "5");
    return `/setup?mode=${mode}&body_focus=${focus}&duration=${duration}`;
  }

  async function togglePauseResume() {
    if (!lastSession) return;
    try {
      const state = String(lastSession.state || "IDLE");
      const action = lastSession.paused || state === "IDLE" ? "start" : "pause";
      const status = await postAction(action);
      consumeStatus(status);
    } catch (error) {
      console.error(error);
    }
  }

  async function nextStretch() {
    if (!lastSession) return;
    const total = sessionTotal(lastSession);
    const index = sessionIndex(lastSession);
    if (index >= total - 1) return;
    try {
      const status = await postAction("next");
      if (status && status.session) previewIndex = sessionIndex(status.session);
      consumeStatus(status);
    } catch (error) {
      console.error(error);
    }
  }

  async function resetSession() {
    if (!lastSession) return;
    try {
      advanceInFlight = false;
      previewIndex = null;
      lastDoneIndex = null;
      stretchScores = [];
      lastHardwareFeedback = "";
      const status = await postAction("reset");
      consumeStatus(status);
    } catch (error) {
      console.error(error);
    }
  }

  window.addEventListener("stretchsense:hardware", (event) => {
    const action = event.detail && event.detail.action;
    if (action === "CONFIRM" || action === "CONFIRM_LONG") togglePauseResume();
    if (action === "ALT") nextStretch();
    if (action === "ALT_LONG") resetSession();
    if (action === "BACK_LONG") window.location.href = setupUrl();
    if (action === "BACK" && lastSession && lastSession.state === "DONE") window.location.href = setupUrl();
  });

  document.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const action = button.dataset.action;
      try {
        const status = await postAction(action);
        consumeStatus(status);
      } catch (error) {
        console.error(error);
      }
    });
  });

  if (debugEnabled && els.debugPanel) {
    els.debugPanel.classList.add("visible");
  }

  refreshStatus().then(startIfIdle);
  window.setInterval(refreshStatus, 500);
})();
