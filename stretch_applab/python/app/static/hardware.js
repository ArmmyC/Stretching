/* Shared YUEDMAI hardware action bridge. */
(function () {
  "use strict";

  const eventName = "YUEDMAI:hardware";
  const nanoEventName = "YUEDMAI:nano-imu";
  let socket = null;
  let reconnectTimer = null;
  let lastFeedback = "";

  function emit(action, value, source) {
    window.dispatchEvent(new CustomEvent(eventName, {
      detail: {
        action,
        value: Number(value || 0),
        source: source || "browser",
        timestamp: Date.now() / 1000,
      },
    }));
  }

  function emitNanoImu(payload, source) {
    window.dispatchEvent(new CustomEvent(nanoEventName, {
      detail: {
        ...(payload || {}),
        source: source || "uno_q_ble",
        timestamp: Date.now() / 1000,
      },
    }));
  }

  function sendFeedback(payload) {
    const body = JSON.stringify(payload || {});
    if (body === lastFeedback) return;
    lastFeedback = body;
    fetch("/api/hardware/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      keepalive: true,
    }).catch(() => {});
  }

  function connect() {
    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) return;
    const scheme = window.location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${scheme}://${window.location.host}/ws/hardware`);

    socket.onmessage = (message) => {
      try {
        const data = JSON.parse(message.data);
        if (data.type === "hardware_event" && data.action) {
          emit(data.action, data.value, data.source || "uno_q");
        } else if (data.type === "nano_imu") {
          emitNanoImu(data.nano_imu || {}, data.source || "uno_q_ble");
        }
      } catch (error) {
        console.error(error);
      }
    };

    socket.onclose = () => {
      window.clearTimeout(reconnectTimer);
      reconnectTimer = window.setTimeout(connect, 1200);
    };
  }

  function actionForKey(event) {
    if (event.altKey || event.ctrlKey || event.metaKey) return null;
    if (event.key === "ArrowLeft" || event.key === "ArrowUp") return "PREV";
    if (event.key === "ArrowRight" || event.key === "ArrowDown") return "NEXT";
    if (event.key === "Enter" || event.key === " ") return "CONFIRM";
    if (event.key === "Backspace" || event.key === "Escape") return "BACK";
    if (event.key.toLowerCase() === "n") return "ALT";
    return null;
  }

  window.addEventListener("keydown", (event) => {
    const action = actionForKey(event);
    if (!action) return;
    event.preventDefault();
    emit(action, 0, "keyboard");
  });

  window.StretchHardware = {
    eventName,
    nanoEventName,
    emit,
    emitNanoImu,
    sendFeedback,
  };

  connect();
})();
