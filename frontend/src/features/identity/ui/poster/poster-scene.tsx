import { useRef, useState } from "react";

import { useTranslations } from "use-intl";

import { createPosterVoices } from "../../model/poster-voices";
import { PosterCast } from "./poster-cast";
import { PosterPill } from "./poster-pill";
import { SPEAKER_TEXT, TALK } from "./poster-script";
import { PosterFacts, PosterLeo } from "./poster-story";
import { PosterTranscript } from "./poster-transcript";
import { useChaosField } from "./use-chaos-field";
import { useLeoNote } from "./use-leo-note";

const RAIL = "mb-[0.6em] font-medium text-[clamp(10px,1.07cqi,13px)] text-muted-foreground";

/**
 * Сцена афиши: сумбурная планёрка → Shosai поверх встречи → лента расшифровки по говорящим → факты → напоминание
 * Leo. Бесконечно живут только сумбур, лента и эквалайзер; история (факты и Leo) проигрывается один раз.
 */
export function PosterScene() {
  const t = useTranslations("identityPoster");
  const chaos = useRef<HTMLDivElement>(null);
  const [voices] = useState(createPosterVoices);
  const note = useLeoNote();
  const lines = TALK.map(([line]) => t(`talk.${line}`));
  const rows = TALK.map(([line, speaker]) => ({
    name: t(`cast.${speaker}`),
    tone: SPEAKER_TEXT[speaker],
    text: t(`talk.${line}`),
  }));
  useChaosField(chaos, lines, voices.heard);

  return (
    <div className="mt-[2.4cqi] flex min-h-0 flex-1 flex-col">
      <div className={RAIL}>{t("rails.meeting")}</div>
      <div
        ref={chaos}
        className="mask-[linear-gradient(to_right,transparent,black_10%,black_90%,transparent)] relative min-h-[11cqi] flex-auto overflow-hidden"
      />
      <PosterPill voices={voices} answer={t(`leo.${note[0]}.body`)} ask={t("ask.placeholder")} />
      <div className={RAIL}>{t("rails.speakers")}</div>
      <PosterCast />
      <PosterTranscript rows={rows} />
      <PosterFacts />
      <PosterLeo note={note} />
    </div>
  );
}
