import { useSyncExternalStore } from "react";

import { ArrowUp } from "lucide-react";
import { ThinkingOrb } from "thinking-orbs";

import type { PosterVoices } from "../../model/poster-voices";

const BUBBLE = "m-0 rounded-2xl border bg-card px-3 py-2 text-sm leading-relaxed";

/**
 * Панель Leo над кнопкой — как в кабинете: заголовок со сферой, то, что звучит прямо сейчас, и ответ Leo. Видна по
 * наведению; вся афиша — декорация, поэтому здесь нет ни полей, ни кнопок, только их вид.
 */
export function PosterPeek({ voices, answer, ask }: { voices: PosterVoices; answer: string; ask: string }) {
  const recent = useSyncExternalStore(voices.subscribe, voices.recent);
  return (
    <div className="absolute end-[calc(100%+12px)] top-1/2 z-10 hidden w-[min(380px,42cqi)] -translate-y-1/2 flex-col gap-3 rounded-2xl border bg-background p-3 text-start shadow-2xl group-hover/pill:flex">
      <div className="flex items-center justify-center gap-2 pt-0.5">
        <span className="flex [&_canvas]:size-6!">
          <ThinkingOrb state="breathing" size={32} />
        </span>
        <span className="font-medium text-sm">Leo</span>
      </div>
      {/* Расшифровка того, что звучит прямо сейчас: реплики разных людей по разные стороны, как в ленте встречи. */}
      <div className="flex flex-col gap-2">
        {recent.map(({ id, line }, position) => (
          <div key={id} className={position === 1 ? "flex justify-end" : "flex"}>
            <p className={`${BUBBLE} max-w-[calc(100%-40px)] bg-card/40 text-foreground/80`}>{line}</p>
          </div>
        ))}
      </div>
      <p className={BUBBLE}>{answer}</p>
      <div className="flex items-center gap-2 rounded-xl border bg-card/40 py-1.5 ps-3 pe-1.5">
        <span className="min-w-0 flex-1 truncate text-muted-foreground text-sm">{ask}</span>
        <span className="grid size-7 flex-none place-items-center rounded-full bg-primary text-primary-foreground">
          <ArrowUp className="size-4" />
        </span>
      </div>
    </div>
  );
}
