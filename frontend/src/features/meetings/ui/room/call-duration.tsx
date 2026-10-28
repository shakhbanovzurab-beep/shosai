import { useSyncExternalStore } from "react";

import { useTranslations } from "use-intl";

import { callClock } from "../../domain/call-duration";

const SECOND_MS = 1_000;

// Тик на каждой секунде часов: перерисовываются только эти часы, а не весь звонок.
function subscribe(onChange: () => void) {
  const timer = window.setInterval(onChange, SECOND_MS);
  return () => window.clearInterval(timer);
}

const getSnapshot = () => Math.floor(Date.now() / SECOND_MS) * SECOND_MS;

/** Сколько идёт встреча — часы в шапке звонка, как в Zoom; пока сервер звонков не назвал начало, их нет. */
export function CallDuration({ startedAt }: { startedAt: number | null }) {
  const t = useTranslations("meetingRoom");
  const now = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  if (startedAt === null) return null;
  const seconds = Math.max(0, Math.floor((now - startedAt) / SECOND_MS));
  return (
    <span role="timer" className="tabular-nums">
      <span className="sr-only">{t("header.duration")} </span>
      <time dateTime={`PT${seconds}S`}>{callClock(startedAt, now)}</time>
    </span>
  );
}
