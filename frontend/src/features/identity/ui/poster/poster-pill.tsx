import { ThinkingOrb } from "thinking-orbs";

import type { PosterVoices } from "../../model/poster-voices";
import { PosterPeek } from "./poster-peek";
import { useVoiceBars } from "./use-voice-bars";

const BARS = ["first", "second", "third", "fourth", "fifth"] as const;
const RESTING = { transform: "scaleY(0.12)" } as const;

/**
 * Свёрнутый Shosai поверх встречи: сфера Leo, как в кабинете, и эквалайзер, который слушает речь. По наведению
 * раскрывается панель Leo с репликами встречи и его ответом.
 */
export function PosterPill({ voices, answer, ask }: { voices: PosterVoices; answer: string; ask: string }) {
  const { bars, host } = useVoiceBars(BARS.length);
  return (
    <div className="group/pill relative my-[1.6cqi] self-center">
      {/* Пока звучит фраза, пилюля мягко светится: Shosai слушает. */}
      <div
        ref={host}
        className="flex h-19 w-8.5 flex-col items-center justify-center gap-1.5 rounded-full border bg-card/40 shadow-lg backdrop-blur-md transition-shadow duration-500 data-[speaking=true]:shadow-[0_0_28px] data-[speaking=true]:shadow-white/15"
      >
        <span className="flex [&_canvas]:size-7!">
          <ThinkingOrb state="solving" size={32} />
        </span>
        <span className="flex h-6 w-6 items-center justify-center gap-[3px]">
          {BARS.map((bar, index) => (
            <i
              key={bar}
              ref={(node) => {
                bars.current[index] = node;
              }}
              // Начальная высота — тем же transform, что двигает полосу: класс scale-y-* задал бы свойство
              // scale, и оно умножилось бы на transform, прижав полосы к полу.
              style={RESTING}
              className="h-full w-0.5 flex-none rounded-full bg-white/75"
            />
          ))}
        </span>
      </div>
      <PosterPeek voices={voices} answer={answer} ask={ask} />
    </div>
  );
}
