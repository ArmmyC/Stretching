/* YUEDMAI session UI logic.
   Frontend only: consumes existing FastAPI status/control endpoints. */
(function () {
  "use strict";

  const READY_SECONDS = 5;
  const STRETCH_SECONDS = 20;
  const BOUNDARY_READY_HOLD_MS = 900;
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
    boundaryPrecheck: el("boundary-precheck"),
    boundaryTitle: el("boundary-precheck-title"),
    boundaryInstruction: el("boundary-precheck-instruction"),
    boundaryFigure: el("humanoid-boundary"),
    boundaryMeterFill: el("boundary-meter-fill"),
    pausedOverlay: el("paused-overlay"),
    debugPanel: el("debug-panel"),
    cameraStream: el("cam-stream"),
    summarySlideImage: el("summary-slide-image"),
    summarySlideEmpty: el("summary-slide-empty"),
    summarySlideName: el("summary-slide-name"),
    summarySlideScore: el("summary-slide-score"),
    summarySlideCounter: el("summary-slide-counter"),
    summaryQr: el("summary-download-qr"),
    summaryShareUrl: el("summary-share-url"),
    summaryDashboardLink: document.querySelector(".summary-dashboard-link"),
  };

  let autoStartAttempted = false;
  let boundaryPrecheckActive = false;
  let boundaryStartInFlight = false;
  let boundaryReadySince = 0;
  let boundaryProgress = 0;
  let lastBoundarySetup = null;
  let advanceInFlight = false;
  let previewIndex = null;
  let lastDoneIndex = null;
  let stretchScores = [];
  let stretchCaptures = [];
  let summarySlideIndex = 0;
  let summarySlideshowPaused = false;
  let lastSession = null;
  let lastHardwareFeedback = "";
  let lastHardwareActionAt = 0;
  let lastAudioState = "";
  let lastAudioIndex = -1;
  let lastCountdownValue = null;
  let lastCompletedAudioIndex = -1;

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
    els.stage.classList.remove("is-boundary-check", "is-countdown", "is-preview", "is-active", "is-complete");
    if (kind) els.stage.classList.add(kind);
  }

  function recordTotalScore(session) {
    const state = String(session.state || "IDLE");
    const index = sessionIndex(session);
    const score = Math.max(0, Number(session.score || 0));
    if (state === "IDLE" && index === 0) {
      stretchScores = [];
      stretchCaptures = [];
      summarySlideIndex = 0;
      summarySlideshowPaused = false;
      renderSummaryCaptures();
    }
    if (score > 0) stretchScores[index] = Math.max(stretchScores[index] || 0, score);
    return stretchScores.reduce((total, value) => total + Math.max(0, Number(value || 0)), 0);
  }

  function renderSummaryCaptures() {
    const captures = stretchCaptures.filter(Boolean);
    if (summarySlideIndex >= captures.length) summarySlideIndex = 0;

    const capture = captures[summarySlideIndex];
    show(els.summarySlideImage, Boolean(capture));
    show(els.summarySlideEmpty, !capture);

    if (capture && els.summarySlideImage) {
      els.summarySlideImage.src = capture.dataUrl;
      els.summarySlideImage.alt = `${capture.name} photo`;
    }
    if (els.summarySlideName) els.summarySlideName.textContent = capture ? capture.name : "Waiting for photos";
    if (els.summarySlideScore) els.summarySlideScore.textContent = capture ? `${capture.score} pts` : "0 pts";
    if (els.summarySlideCounter) {
      els.summarySlideCounter.textContent = captures.length ? `${summarySlideIndex + 1} / ${captures.length}` : "0 / 0";
    }
  }

  function nextSummarySlide() {
    const captures = stretchCaptures.filter(Boolean);
    if (!captures.length) return;
    summarySlideIndex = (summarySlideIndex + 1) % captures.length;
    renderSummaryCaptures();
  }

  function previousSummarySlide() {
    const captures = stretchCaptures.filter(Boolean);
    if (!captures.length) return;
    summarySlideIndex = (summarySlideIndex - 1 + captures.length) % captures.length;
    renderSummaryCaptures();
  }

  function updateCaptureShare(status) {
    const captures = status && status.captures;
    if (!captures) return;
    if (els.summaryQr && captures.qr_url && els.summaryQr.getAttribute("src") !== captures.qr_url) {
      els.summaryQr.src = captures.qr_url;
    }
    if (els.summaryShareUrl && captures.share_url) {
      els.summaryShareUrl.textContent = captures.share_url;
    }
  }

  async function uploadCapture(capture) {
    if (capture.uploading || capture.uploaded) return;
    capture.uploading = true;
    try {
      const response = await fetch("/api/session/captures", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          index: capture.index,
          name: capture.name,
          score: capture.score,
          image: capture.dataUrl,
        }),
      });
      capture.uploading = false;
      capture.uploaded = response.ok;
      if (response.ok) {
        const payload = await response.json();
        updateCaptureShare(payload);
      }
    } catch (error) {
      capture.uploading = false;
      console.error(error);
    }
  }

  function captureStretchImage(session) {
    const state = String(session.state || "IDLE");
    if (state !== "GOOD" && state !== "DONE") return;

    const index = sessionIndex(session);
    if (stretchCaptures[index]) {
      const score = Math.max(stretchCaptures[index].score || 0, Number(session.score || 0));
      if (score !== stretchCaptures[index].score) {
        stretchCaptures[index].score = score;
        stretchCaptures[index].uploaded = false;
        renderSummaryCaptures();
        uploadCapture(stretchCaptures[index]);
      }
      return;
    }

    const image = els.cameraStream;
    if (!image || !image.complete || !image.naturalWidth || !image.naturalHeight) return;

    try {
      const canvas = document.createElement("canvas");
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      const context = canvas.getContext("2d");
      if (!context) return;
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      const dataUrl = canvas.toDataURL("image/jpeg", 0.86);
      stretchCaptures[index] = {
        index,
        name: session.current_stretch || `Stretch ${index + 1}`,
        score: Math.max(0, Number(session.score || 0)),
        dataUrl,
        capturedAt: Date.now(),
      };
      renderSummaryCaptures();
      uploadCapture(stretchCaptures[index]);
    } catch (error) {
      console.error(error);
    }
  }

  function updateOverlays(session, totalScore) {
    const state = String(session.state || "IDLE");
    const index = sessionIndex(session);
    const total = sessionTotal(session);
    const count = readyCountdown(session);
    const isPreview = state === "READY" && previewIndex === index && index > 0;
    const isCountdown = state === "READY" && !isPreview;
    const isComplete = state === "DONE" && index >= total - 1;
    const isPaused = Boolean(session.paused) && !isComplete;

    if (boundaryPrecheckActive) {
      show(els.boundaryPrecheck, true);
      show(els.pausedOverlay, false);
      show(els.countdownOverlay, false);
      show(els.nextPreview, false);
      show(els.completeOverlay, false);
      setStageClass("is-boundary-check");
      return;
    }

    show(els.boundaryPrecheck, false);
    show(els.pausedOverlay, isPaused);
    show(els.countdownOverlay, isCountdown);
    show(els.nextPreview, isPreview);
    show(els.completeOverlay, isComplete);

    if (els.countdownNumber) els.countdownNumber.textContent = String(count);
    if (els.countdownLabel) els.countdownLabel.textContent = session.current_stretch || "Get ready";
    if (els.nextName) els.nextName.textContent = session.current_stretch || "Next stretch";
    if (els.nextCountdownNumber) els.nextCountdownNumber.textContent = String(count);
    if (els.completeScore) els.completeScore.textContent = String(totalScore);
    if (els.completeMeta) {
      const photoCount = stretchCaptures.filter(Boolean).length;
      const photoLabel = photoCount === 1 ? "photo" : "photos";
      els.completeMeta.textContent = `${total} stretches completed - ${photoCount} ${photoLabel} captured`;
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
    if (boundaryPrecheckActive) {
      const setup = lastBoundarySetup || {};
      const payload = {
        page: "session",
        state: "boundary_check",
        selection: setup.label || "Boundary check",
        value: Math.round(boundaryProgress * 100),
      };
      const serialized = JSON.stringify(payload);
      if (serialized === lastHardwareFeedback) return;
      lastHardwareFeedback = serialized;
      window.StretchHardware.sendFeedback(payload);
      return;
    }

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

  function applyBoundaryPrecheck(setup) {
    if (!setup) return;
    lastBoundarySetup = setup;

    const ready = Boolean(setup.ready);
    const badgeClass = setup.badge_class || (ready ? "ok" : "warn");
    const label = setup.label || (ready ? "Ready" : "Checking position");
    const instruction = setup.instruction || (ready ? "Boundary check passed" : "Fit inside the guide");

    if (els.boundaryTitle) els.boundaryTitle.textContent = label;
    if (els.boundaryInstruction) els.boundaryInstruction.textContent = instruction;
    if (els.boundaryFigure) {
      els.boundaryFigure.classList.remove("ready", "info", "warn", "bad");
      els.boundaryFigure.classList.add(ready ? "ready" : badgeClass);
    }
    if (els.boundaryMeterFill) {
      els.boundaryMeterFill.style.width = `${Math.round(boundaryProgress * 100)}%`;
    }
  }

  async function beginBoundaryPrecheck(status) {
    if (boundaryPrecheckActive || boundaryStartInFlight || autoStartAttempted) return;

    if (status && status.session && String(status.session.state || "IDLE") !== "IDLE") {
      stretchScores = [];
      stretchCaptures = [];
      summarySlideIndex = 0;
      summarySlideshowPaused = false;
      previewIndex = null;
      lastDoneIndex = null;
      lastHardwareFeedback = "";
      renderSummaryCaptures();
      status = await postAction("reset");
    }

    boundaryPrecheckActive = true;
    boundaryReadySince = 0;
    boundaryProgress = 0;
    applyBoundaryPrecheck(status && status.setup);
    show(els.boundaryPrecheck, true);
    setStageClass("is-boundary-check");
  }

  async function maybeStartAfterBoundary(status) {
    if (!boundaryPrecheckActive || boundaryStartInFlight || autoStartAttempted) return;

    const setup = (status && status.setup) || {};
    const now = performance.now();
    if (setup.ready) {
      if (!boundaryReadySince) boundaryReadySince = now;
      boundaryProgress = Math.max(0, Math.min(1, (now - boundaryReadySince) / BOUNDARY_READY_HOLD_MS));
    } else {
      boundaryReadySince = 0;
      boundaryProgress = 0;
    }
    applyBoundaryPrecheck(setup);

    if (boundaryProgress < 1) return;

    boundaryStartInFlight = true;
    autoStartAttempted = true;
    try {
      const startedStatus = await postAction("start");
      boundaryPrecheckActive = false;
      boundaryStartInFlight = false;
      boundaryReadySince = 0;
      boundaryProgress = 0;
      show(els.boundaryPrecheck, false);
      consumeStatus(startedStatus);
    } catch (error) {
      boundaryStartInFlight = false;
      autoStartAttempted = false;
      console.error(error);
    }
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

  function updateSessionAudio(session) {
    if (!window.StretchAudio || !session) return;

    const state = String(session.state || "IDLE");
    const index = sessionIndex(session);
    const total = sessionTotal(session);
    const paused = Boolean(session.paused);
    const count = state === "READY" ? readyCountdown(session) : null;
    const stateChanged = state !== lastAudioState || index !== lastAudioIndex;

    if (state === "IDLE") {
      lastCountdownValue = null;
      lastCompletedAudioIndex = -1;
      window.StretchAudio.stop("stretch");
    }

    if (paused) {
      window.StretchAudio.pause("stretch");
    } else if (state === "HOLD" || state === "GOOD") {
      window.StretchAudio.playLoop("stretch");
    } else {
      window.StretchAudio.stop("stretch");
    }

    if (state === "READY" && (stateChanged || count !== lastCountdownValue)) {
      window.StretchAudio.play("countdown");
      lastCountdownValue = count;
    }

    if (state === "DONE" && lastCompletedAudioIndex !== index) {
      window.StretchAudio.play("complete");
      lastCompletedAudioIndex = index;
      if (index >= total - 1) window.StretchAudio.stop("stretch");
    }

    if (state !== "READY") lastCountdownValue = null;
    lastAudioState = state;
    lastAudioIndex = index;
  }

  function setSession(session) {
    if (!session) return;
    lastSession = session;
    const totalScore = recordTotalScore(session);
    captureStretchImage(session);
    updateHud(session, totalScore);
    updateOverlays(session, totalScore);
    sendHardwareFeedback(session, totalScore);
    updateSessionAudio(session);
    maybeAdvance(session);
  }

  function consumeStatus(status) {
    setCamera(status.camera || {});
    updateCaptureShare(status);
    if (boundaryPrecheckActive) applyBoundaryPrecheck(status.setup || {});
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
      await maybeStartAfterBoundary(status);
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
    try {
      await beginBoundaryPrecheck(status);
      await maybeStartAfterBoundary(status);
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

  function isSessionComplete(session) {
    if (!session) return false;
    return String(session.state || "IDLE") === "DONE" && sessionIndex(session) >= sessionTotal(session) - 1;
  }

  function normalizeHardwareAction(action) {
    const raw = String(action || "").toUpperCase();
    const aliases = {
      BUTTON_A: "CONFIRM",
      BUTTON_B: "BACK",
      BUTTON_C: "ALT",
      BUTTON_A_LONG: "CONFIRM_LONG",
      BUTTON_B_LONG: "BACK_LONG",
      BUTTON_C_LONG: "ALT_LONG",
      KNOB_PRESS: "CONFIRM",
      KNOB_PRESS_LONG: "CONFIRM_LONG",
      KNOB_RIGHT: "NEXT",
      KNOB_LEFT: "PREV",
    };
    return aliases[raw] || raw;
  }

  function hardwareActionReady() {
    const now = performance.now();
    if (now - lastHardwareActionAt < 180) return false;
    lastHardwareActionAt = now;
    return true;
  }

  function openDashboardPlaceholder() {
    if (els.summaryDashboardLink && els.summaryDashboardLink.href) {
      window.location.href = els.summaryDashboardLink.href;
    }
  }

  async function togglePauseResume() {
    if (boundaryPrecheckActive) return;
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
    if (boundaryPrecheckActive) return;
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
    if (boundaryPrecheckActive) return;
    if (!lastSession) return;
    try {
      advanceInFlight = false;
      previewIndex = null;
      lastDoneIndex = null;
      stretchScores = [];
      stretchCaptures = [];
      summarySlideIndex = 0;
      summarySlideshowPaused = false;
      lastHardwareFeedback = "";
      renderSummaryCaptures();
      const status = await postAction("reset");
      consumeStatus(status);
    } catch (error) {
      console.error(error);
    }
  }

  function handleHardwareAction(event) {
    const action = normalizeHardwareAction(event.detail && event.detail.action);
    if (!hardwareActionReady()) return;

    if (boundaryPrecheckActive) {
      if (action === "BACK" || action === "BACK_LONG") window.location.href = setupUrl();
      return;
    }

    if (isSessionComplete(lastSession)) {
      if (action === "CONFIRM" || action === "CONFIRM_LONG") openDashboardPlaceholder();
      if (action === "ALT" || action === "NEXT") {
        nextSummarySlide();
      }
      if (action === "PREV") previousSummarySlide();
      if (action === "ALT_LONG") resetSession();
      if (action === "BACK" || action === "BACK_LONG") window.location.href = setupUrl();
      return;
    }

    if (action === "CONFIRM" || action === "CONFIRM_LONG") togglePauseResume();
    if (action === "ALT") nextStretch();
    if (action === "ALT_LONG") resetSession();
    if (action === "BACK_LONG") window.location.href = setupUrl();
    if (action === "BACK" && lastSession && lastSession.state === "DONE") window.location.href = setupUrl();
  }

  window.addEventListener("YUEDMAI:hardware", handleHardwareAction);
  window.addEventListener("yuedmai:hardware", handleHardwareAction);
  window.addEventListener("stretchsense:hardware", handleHardwareAction);

  document.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (boundaryPrecheckActive) return;
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
  window.setInterval(() => {
    if (!isSessionComplete(lastSession) || summarySlideshowPaused) return;
    nextSummarySlide();
  }, 3000);
})();
