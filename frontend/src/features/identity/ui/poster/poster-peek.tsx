import { useSyncExternalStore } from "react";

import { Sparkles } from "lucide-react";

import type { PosterVoices } from "../../model/poster-voices";

const BUBBLE =
  "m-0 max-w-[calc(100%-40px)] rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-[0.84375rem] text-white leading-normal";

/**
 * Панель над пилюлей — так выглядит Shosai поверх встречи: то, что звучит прямо сейчас, и ответ Leo. Видна по
 * наведению; вся афиша — декорация, поэтому здесь нет ни полей, ни кнопок, только их вид.
 */
export function PosterPeek({
  voices,
  answer,
  ask,
}: {
  voices: PosterVoices;
  answer: string;
  ask: { placeholder: string; button: string };
}) {
  const recent = useSyncExternalStore(voices.subscribe, voices.recent);
  return (
    <div className="absolute end-[calc(100%+11px)] -top-px z-10 hidden w-[min(400px,42cqi)] flex-col gap-2.5 rounded-[20px] border border-white/10 bg-zinc-950/90 p-3 text-start shadow-2xl group-hover/pill:flex">
      <div className="flex flex-col gap-2">
        {recent.map(({ id, line }, position) => (
          <div key={id} className={position === 1 ? "flex justify-end" : "flex"}>
            <p className={BUBBLE}>{line}</p>
          </div>
        ))}
        <div className="flex">
          <p className={`${BUBBLE} border-amber-400/35 bg-amber-400/10`}>{answer}</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <div className="min-w-0 flex-1 rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-[0.84375rem] text-white/40">
          {ask.placeholder}
        </div>
        <div className="flex flex-none items-center gap-1.5 rounded-full border border-white/10 bg-white/15 px-3 py-2.5 font-semibold text-[0.78125rem] text-white">
          <Sparkles className="size-3.5" />
          {ask.button}
        </div>
      </div>
    </div>
  );
}
