import { ThinkingOrb } from "thinking-orbs";
import { useFormatter, useTranslations } from "use-intl";

import { CALENDAR_DAY } from "@/i18n/calendar-days";

import { FACTS, type LeoNoteTime, meetingClock } from "./poster-script";

// Факты и Leo появляются один раз, когда встреча «прозвучала», и дальше стоят: у истории нет цикла.
const REVEAL = "fade-in fill-mode-both animate-in delay-[2600ms] duration-700 motion-reduce:animate-none";
const RAIL = "mt-[1.6cqi] mb-[0.6em] font-medium text-[clamp(10px,1.07cqi,13px)] text-muted-foreground";
// Карточки — как сообщения Leo в кабинете: тонкая рамка и фон карточки из токенов темы.
const CARD = "rounded-2xl border bg-card";

/** Что следует из встречи: факты с отметкой времени. */
export function PosterFacts() {
  const t = useTranslations("identityPoster");
  return (
    <>
      <div className={RAIL}>{t("rails.facts")}</div>
      <div className="flex gap-[1.28cqi]">
        {FACTS.map(([fact, second]) => (
          <div
            key={fact}
            className={`relative min-w-0 flex-1 px-[0.95em] py-[0.8em] font-medium text-[clamp(10px,1.4cqi,17px)] text-foreground/90 leading-[1.35] ${CARD} ${REVEAL}`}
          >
            <span className="absolute end-[0.8em] top-[0.7em] font-mono text-[clamp(7px,1.02cqi,12px)] text-muted-foreground tabular-nums">
              {meetingClock(second)}
            </span>
            <span className="mb-[0.35em] block font-medium text-[clamp(8px,1.07cqi,13px)] text-muted-foreground">
              {t(`facts.${fact}.label`)}
            </span>
            {t(`facts.${fact}.value`)}
          </div>
        ))}
      </div>
    </>
  );
}

/** Напоминание Leo — ради него всё остальное и делалось. */
export function PosterLeo({ note: [note, hour, minute] }: { note: LeoNoteTime }) {
  const t = useTranslations("identityPoster");
  const format = useFormatter();
  return (
    <>
      <div className={RAIL}>{t("rails.leo")}</div>
      <div className={`relative flex items-start gap-[1.4cqi] px-[1.2em] py-[1.05em] ${CARD} ${REVEAL}`}>
        {/* Leo выглядит так же, как в шапке его панели в кабинете: дышащая сфера. */}
        <span className="flex flex-none [&_canvas]:size-8!">
          <ThinkingOrb state="breathing" size={32} />
        </span>
        <div key={note} className="fade-in relative animate-in duration-500 motion-reduce:animate-none">
          <div className="font-medium text-[clamp(8px,1.07cqi,13px)] text-muted-foreground">
            {t(`leo.${note}.when`, {
              // Время-образец на часах постера, а не момент: собрано и печатается в UTC.
              time: format.dateTime(new Date(Date.UTC(2026, 0, 1, hour, minute)), "time", CALENDAR_DAY),
            })}
          </div>
          <div className="mt-[0.25em] text-[clamp(11px,1.6cqi,19px)] text-foreground leading-[1.45]">
            {t(`leo.${note}.body`)}
          </div>
        </div>
      </div>
    </>
  );
}
