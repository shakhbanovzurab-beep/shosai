import { useEffect, useState } from "react";

/** Обратный отсчёт в целых секундах: сколько ждать до повторной отправки кода. */
export function useCountdown(initialSeconds: number) {
  const [deadline, setDeadline] = useState(() => Date.now() + initialSeconds * 1000);
  const [now, setNow] = useState(() => Date.now());
  const remaining = Math.max(0, Math.ceil((deadline - now) / 1000));

  useEffect(() => {
    if (remaining === 0) return;
    const timer = window.setTimeout(() => setNow(Date.now()), 1000);
    return () => window.clearTimeout(timer);
  }, [remaining]);

  const restart = (seconds: number) => {
    const started = Date.now();
    setNow(started);
    setDeadline(started + seconds * 1000);
  };

  return { remaining, restart };
}
