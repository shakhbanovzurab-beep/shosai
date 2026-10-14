import { useFormatter, useTranslations } from "use-intl";

import { SHARE, SPEAKER_CHIP, SPEAKERS } from "./poster-script";

/** Кто был на встрече и какую долю времени говорил — итог разметки по голосам одной строкой. */
export function PosterCast() {
  const t = useTranslations("identityPoster");
  const format = useFormatter();
  return (
    <div className="flex flex-wrap gap-x-[2.4em] gap-y-[0.6em]">
      {SPEAKERS.map((speaker) => {
        const name = t(`cast.${speaker}`);
        return (
          <div
            key={speaker}
            className="flex items-center gap-[0.55em] text-[clamp(11px,1.39cqi,17px)] text-foreground/80"
          >
            <span
              className={`grid size-[2em] flex-none place-items-center rounded-full font-extrabold text-[clamp(9px,1.18cqi,14px)] text-zinc-950 ${SPEAKER_CHIP[speaker]}`}
            >
              {Array.from(name)[0]}
            </span>
            {name}
            <span className="font-bold font-mono text-[clamp(9px,1.18cqi,14px)] text-muted-foreground tabular-nums">
              {format.number(SHARE[speaker], { style: "percent" })}
            </span>
          </div>
        );
      })}
    </div>
  );
}
