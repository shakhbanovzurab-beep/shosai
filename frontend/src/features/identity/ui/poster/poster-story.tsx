import { Zap } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { FACTS, type LeoNoteTime, meetingClock } from "./poster-script";

// Факты и Leo появляются один раз, когда встреча «прозвучала», и дальше стоят: у истории нет цикла.
const REVEAL = "fade-in fill-mode-both animate-in delay-[2600ms] duration-700 motion-reduce:animate-none";
const RAIL =
  "mt-[1.6cqi] mb-[0.5em] font-bold font-mono text-[clamp(9px,1.07cqi,13px)] text-muted-foreground/70 uppercase tracking-[0.14em]";

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
            className={`relative min-w-0 flex-1 rounded-[14px] border-2 border-zinc-950 bg-yellow-300 px-[0.85em] py-[0.7em] font-semibold text-[clamp(10px,1.5cqi,18px)] text-zinc-950 leading-[1.32] shadow-[4px_4px_0_0] shadow-stone-200/20 ${REVEAL}`}
          >
            <span className="absolute end-[0.7em] top-[0.6em] font-bold font-mono text-[clamp(7px,1.02cqi,12px)] opacity-50">
              {meetingClock(second)}
            </span>
            <span className="mb-[0.25em] block font-bold font-mono text-[clamp(7px,1.02cqi,12px)] uppercase tracking-[0.12em] opacity-60">
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
      <div
        className={`flex items-start gap-[1.5cqi] rounded-[18px] border-2 border-stone-100 bg-stone-100 px-[1.2em] py-[1.1em] text-zinc-950 shadow-[6px_6px_0_0] shadow-yellow-300 rtl:shadow-[-6px_6px_0_0] ${REVEAL}`}
      >
        <div className="grid size-[2.6em] flex-none place-items-center rounded-full bg-zinc-950 text-[clamp(11px,1.5cqi,18px)] text-yellow-300">
          <Zap className="size-[1.15em] fill-current" />
        </div>
        <div key={note} className="fade-in animate-in duration-500 motion-reduce:animate-none">
          <div className="font-bold font-mono text-[clamp(8px,1.07cqi,13px)] text-stone-600 tracking-[0.14em]">
            {t(`leo.${note}.when`, { time: format.dateTime(new Date(Date.UTC(2026, 0, 1, hour, minute)), "time") })}
          </div>
          <div className="mt-[0.2em] font-medium text-[clamp(11px,1.66cqi,20px)] leading-[1.4]">
            {t(`leo.${note}.body`)}
          </div>
        </div>
      </div>
    </>
  );
}
