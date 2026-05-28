/* Setup page hardware navigation. */
(function () {
  "use strict";

  const form = document.getElementById("config-form");
  const startButton = document.querySelector(".start-session-btn");
  const hiddenInputs = {
    mode: document.getElementById("f-mode"),
    body_focus: document.getElementById("f-body-focus"),
    duration: document.getElementById("f-duration"),
  };

  const setupState = {
    mode: hiddenInputs.mode ? hiddenInputs.mode.value : "before",
    body_focus: hiddenInputs.body_focus ? hiddenInputs.body_focus.value : "full",
    duration: hiddenInputs.duration ? hiddenInputs.duration.value : "5",
  };

  const focusItems = Array.from(document.querySelectorAll(".segmented button, .start-session-btn"));
  let focusIndex = Math.max(0, focusItems.findIndex((item) => item.classList.contains("active")));

  function syncSetupInputs() {
    if (hiddenInputs.mode) hiddenInputs.mode.value = setupState.mode;
    if (hiddenInputs.body_focus) hiddenInputs.body_focus.value = setupState.body_focus;
    if (hiddenInputs.duration) hiddenInputs.duration.value = setupState.duration;
  }

  function selectedItem() {
    return focusItems[focusIndex] || null;
  }

  function selectionName() {
    const item = selectedItem();
    if (!item) return "";
    const group = item.closest(".segmented");
    if (!group) return "start";
    return `${group.dataset.group}:${item.dataset.value}`;
  }

  function sendFeedback() {
    if (!window.StretchHardware) return;
    window.StretchHardware.sendFeedback({
      page: "setup",
      state: "configure",
      selection: selectionName(),
      value: focusIndex,
    });
  }

  function renderFocus() {
    focusItems.forEach((item, index) => {
      item.classList.toggle("hardware-focus", index === focusIndex);
    });
    sendFeedback();
  }

  function setFocusToItem(item) {
    const index = focusItems.indexOf(item);
    if (index >= 0) {
      focusIndex = index;
      renderFocus();
    }
  }

  function selectOption(button) {
    const segmented = button.closest(".segmented");
    if (!segmented) return;
    segmented.querySelectorAll("button").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    setupState[segmented.dataset.group] = button.dataset.value;
    syncSetupInputs();
    sendFeedback();
  }

  function move(delta) {
    focusIndex = (focusIndex + delta + focusItems.length) % focusItems.length;
    renderFocus();
  }

  function confirm() {
    const item = selectedItem();
    if (!item) return;
    if (item === startButton) {
      submitForm();
      return;
    }
    selectOption(item);
  }

  function submitForm() {
    if (form.requestSubmit) form.requestSubmit();
    else form.submit();
  }

  function back() {
    const mode = encodeURIComponent(setupState.mode || "before");
    window.location.href = `/?mode=${mode}`;
  }

  document.querySelectorAll(".segmented").forEach((segmented) => {
    segmented.addEventListener("click", (event) => {
      const button = event.target.closest("button");
      if (!button) return;
      selectOption(button);
      setFocusToItem(button);
    });
  });

  if (startButton) {
    startButton.addEventListener("focus", () => setFocusToItem(startButton));
  }

  window.addEventListener("YUEDMAI:hardware", (event) => {
    const action = event.detail && event.detail.action;
    if (action === "NEXT") move(1);
    if (action === "PREV") move(-1);
    if (action === "CONFIRM" || action === "CONFIRM_LONG") confirm();
    if (action === "BACK" || action === "BACK_LONG") back();
    if (action === "ALT" || action === "ALT_LONG") submitForm();
  });

  syncSetupInputs();
  renderFocus();
})();
