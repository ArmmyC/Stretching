/* Landing page hardware navigation. */
(function () {
  "use strict";

  const cards = Array.from(document.querySelectorAll(".choice-card"));
  const params = new URLSearchParams(window.location.search);
  const requestedMode = params.get("mode");
  let selectedIndex = Math.max(0, cards.findIndex((card) => card.dataset.mode === requestedMode));

  function selectedCard() {
    return cards[selectedIndex] || null;
  }

  function sendFeedback() {
    const card = selectedCard();
    if (!window.StretchHardware || !card) return;
    window.StretchHardware.sendFeedback({
      page: "landing",
      state: "select_mode",
      selection: card.dataset.mode || "",
      value: selectedIndex,
    });
  }

  function render() {
    cards.forEach((card, index) => {
      const selected = index === selectedIndex;
      card.classList.toggle("hardware-focus", selected);
      card.setAttribute("aria-current", selected ? "true" : "false");
    });
    sendFeedback();
  }

  function move(delta) {
    selectedIndex = (selectedIndex + delta + cards.length) % cards.length;
    render();
  }

  function confirm() {
    const card = selectedCard();
    if (card) window.location.href = card.href;
  }

  cards.forEach((card, index) => {
    card.addEventListener("mouseenter", () => {
      selectedIndex = index;
      render();
    });
    card.addEventListener("focus", () => {
      selectedIndex = index;
      render();
    });
  });

  window.addEventListener("YUEDMAI:hardware", (event) => {
    const action = event.detail && event.detail.action;
    if (action === "NEXT" || action === "PREV") move(1);
    if (action === "CONFIRM" || action === "CONFIRM_LONG") confirm();
  });

  if (cards.length > 0) render();
})();
