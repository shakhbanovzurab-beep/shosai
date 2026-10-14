import { ShosaiMark } from "@/components/shosai-mark";

import type { PosterVoices } from "../../model/poster-voices";
import { PosterPeek } from "./poster-peek";

// Полосы эквалайзера качаются со сдвигом: одна волна голоса, а не четыре одинаковых столбика.
const BARS = ["[animation-delay:0ms]", "[animation-delay:90ms]", "[animation-delay:180ms]", "[animation-delay:270ms]"];

/** Свёрнутый Shosai поверх встречи: знак и эквалайзер голоса; по наведению раскрывается панель с ответом Leo. */
export function PosterPill({
  voices,
  answer,
  ask,
}: {
  voices: PosterVoices;
  answer: string;
  ask: { placeholder: string; button: string };
}) {
  return (
    <div className="group/pill relative my-[1.6cqi] self-center">
      <div className="flex h-19 w-8.5 flex-col items-center justify-center gap-2 rounded-full border border-white/10 bg-zinc-900 shadow-[0_0_46px] shadow-amber-400/20">
        <ShosaiMark className="size-5 text-white/65" />
        <span className="flex h-5 w-5 items-center justify-center gap-0.75">
          {BARS.map((delay) => (
            <i
              key={delay}
              className={`h-[88%] w-0.75 flex-none animate-equalizer rounded-xs bg-amber-400 motion-reduce:scale-y-60 motion-reduce:animate-none ${delay}`}
            />
          ))}
        </span>
      </div>
      <PosterPeek voices={voices} answer={answer} ask={ask} />
    </div>
  );
}
