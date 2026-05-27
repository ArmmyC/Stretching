/* StretchSense — session page UI logic
   Pure UI; talks to FastAPI endpoints:
     GET  /api/status
     POST /api/session/start | /pause | /next | /reset
*/
(function () {
  "use strict";

  const qs = new URLSearchParams(window.location.search);
  const DEBUG = qs.get("debug") === "1";

  const el = (id) => document.getElementById(id);

  // ---- Debug panel toggle ----
  if (DEBUG) el("debug-panel").classList.add("visible");

  // ---- Control buttons ----
  document.querySelectorAll("[data-action]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const action = btn.dataset.action;
      try {
        await fetch(`/api/session/${action}`, { method: "POST" });
      } catch (e) { /* offline ok */ }
    });
  });

  // ---- State styling helper ----
  function setState(state) {
    const pill = el("state-pill");
    pill.dataset.state = state;
    el("state-text").textContent = state;
    el("timer").classList.toggle("hold", state === "HOLD");
    if (DEBUG) el("d-state").textContent = state;
  }

  function setCameraSource(src) {
    const badge = el("cam-source-badge");
    const text = el("cam-source-text");
    badge.className = "badge";
    const map = {
      usb:     { cls: "ok",   label: "USB Camera" },
      phone:   { cls: "info", label: "Phone Camera" },
      waiting: { cls: "warn", label: "Waiting for Phone" },
      none:    { cls: "bad",  label: "No Camera" },
    };
    const m = map[src] || map.none;
    badge.classList.add(m.cls);
    badge.innerHTML = `<span class="pulse"></span><span id="cam-source-text">${m.label}</span>`;
    if (DEBUG) {
      el("d-cam-source").textContent = src;
      el("d-usb").textContent = src === "usb";
      el("d-phone").textContent = src === "phone";
    }
  }

  function fmtTime(s) {
    s = Math.max(0, Math.floor(s));
    const m = Math.floor(s / 60).toString().padStart(2, "0");
    const r = (s % 60).toString().padStart(2, "0");
    return `${m}:${r}`;
  }

  // ---- Status polling ----
  let lastFrameTs = null;
  async function poll() {
    try {
      const r = await fetch("/api/status", { cache: "no-store" });
      if (!r.ok) return;
      const d = await r.json();

      if (d.camera) setCameraSource(d.camera);
      if (d.state) setState(d.state);

      if (d.stretch) {
        if (d.stretch.name) el("stretch-name").textContent = d.stretch.name;
        if (d.stretch.step_label) el("stretch-step").textContent = d.stretch.step_label;
        if (d.stretch.instruction) el("instruction").textContent = d.stretch.instruction;
      }

      if (typeof d.remaining_s === "number") el("timer").textContent = fmtTime(d.remaining_s);

      if (typeof d.progress === "number") {
        const pct = Math.round(d.progress * 100);
        el("progress-bar").style.width = pct + "%";
        el("progress-bar-side").style.width = pct + "%";
        el("progress-pct").textContent = pct + "%";
      }

      if (typeof d.score === "number") {
        el("score-value").textContent = d.score;
        el("score-label").textContent =
          d.score >= 80 ? "Good" : d.score >= 50 ? "Steady" : "Adjust";
      }
      if (typeof d.stability === "number") {
        const s = Math.round(d.stability * 100);
        el("stability-bar").style.width = s + "%";
        el("stability-pct").textContent = s + "%";
      }

      if (d.config) {
        if (d.config.mode)     el("meta-mode").textContent = d.config.mode === "after" ? "After workout" : "Before workout";
        if (d.config.focus)    el("meta-focus").textContent = ({upper:"Upper body",lower:"Lower body",full:"Full body"})[d.config.focus] || d.config.focus;
        if (d.config.duration) el("meta-duration").textContent = d.config.duration + " min";
        if (DEBUG) {
          el("d-mode").textContent = d.config.mode || "—";
          el("d-focus").textContent = d.config.focus || "—";
          el("d-duration").textContent = d.config.duration || "—";
        }
      }

      if (DEBUG) {
        if (d.fps) el("d-fps").textContent = d.fps;
        if (d.frame_w && d.frame_h) el("d-size").textContent = `${d.frame_w}×${d.frame_h}`;
        if (d.frame_ts) { lastFrameTs = d.frame_ts; el("d-frame-ts").textContent = d.frame_ts; }
        if (typeof d.elapsed_s === "number") el("d-elapsed").textContent = d.elapsed_s + "s";
        if (d.forced_camera) el("d-forced").textContent = d.forced_camera;
        if (d.local_url) el("d-url").textContent = d.local_url;
        el("debug-time").textContent = new Date().toLocaleTimeString();
      }
    } catch (e) { /* offline ok */ }
  }

  poll();
  setInterval(poll, 500);
})();
