export async function enableReminderPreview() {
  if (!("Notification" in window)) {
    return "Notifications are not supported in this browser.";
  }

  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    return "Notification permission was not granted.";
  }

  new Notification("YUEDMAI reminder enabled", {
    body: "Daily stretch quest reminders can be connected next.",
  });
  return "Reminder preview enabled.";
}

export async function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) return;
  await navigator.serviceWorker.register("/service-worker.js");
}
