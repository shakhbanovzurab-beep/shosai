"use client";

/** Two soft tones when a phase ends. Silently does nothing where audio isn't allowed yet. */
export function chime() {
  try {
    const context = new AudioContext();
    [880, 1320].forEach((frequency, index) => {
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.frequency.value = frequency;
      oscillator.connect(gain);
      gain.connect(context.destination);
      const at = context.currentTime + index * 0.18;
      gain.gain.setValueAtTime(0.0001, at);
      gain.gain.exponentialRampToValueAtTime(0.18, at + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.5);
      oscillator.start(at);
      oscillator.stop(at + 0.55);
    });
    window.setTimeout(() => void context.close(), 1500);
  } catch {
    // No audio: the toast and the page title still say the phase ended.
  }
}

/**
 * A system notification when the tab is in the background, only if the user already allowed them. The message is
 * in the interface language, so it takes the page's language and direction.
 */
export function notifyIfHidden(message: string) {
  if (typeof Notification === "undefined" || !document.hidden || Notification.permission !== "granted") return;
  const root = document.documentElement;
  try {
    new Notification(message, { lang: root.lang, dir: root.dir === "rtl" ? "rtl" : "ltr" });
  } catch {
    // Some browsers only allow notifications from a service worker.
  }
}
