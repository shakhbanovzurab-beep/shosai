import { useEffect, useEffectEvent, useRef } from "react";

import { meetingClock, prefersReducedMotion, seededRandom } from "./poster-script";

export interface TranscriptRow {
  name: string;
  tone: string;
  text: string;
}

/** Скорость ленты, px/с: медленно настолько, чтобы строку успевали прочесть. */
const SPEED = 16;
const ROW_CLASS = "flex h-(--transcript-row) items-start gap-[0.7em]";
const CLOCK_CLASS =
  "w-[4.4em] flex-none pt-[0.7em] font-bold font-mono text-[clamp(8px,1.12cqi,13px)] text-muted-foreground/70 tabular-nums";
const NAME_CLASS = "w-[10.3cqi] flex-none truncate pt-[0.35em] font-semibold text-[clamp(10px,1.34cqi,16px)]";
const TEXT_CLASS =
  "min-w-0 flex-1 truncate pt-[0.15em] text-[clamp(11px,1.55cqi,19px)] text-foreground/90 leading-[1.4]";

function rowElement(row: TranscriptRow, clock: number): HTMLDivElement {
  const element = document.createElement("div");
  element.className = ROW_CLASS;
  const stamp = document.createElement("span");
  stamp.className = CLOCK_CLASS;
  stamp.textContent = meetingClock(clock);
  const name = document.createElement("span");
  name.className = `${NAME_CLASS} ${row.tone}`;
  name.textContent = row.name;
  const text = document.createElement("span");
  text.className = TEXT_CLASS;
  text.textContent = row.text;
  element.append(stamp, name, text);
  return element;
}

/**
 * Лента расшифровки едет вверх непрерывно: строки уходят сверху и рождаются снизу. Разговор идёт по порядку, а
 * отметка времени растёт и на втором проходе, поэтому лента не выглядит перезапущенной. Движение — через
 * requestAnimationFrame и transform, без перерисовки React.
 */
export function PosterTranscript({ rows }: { rows: readonly TranscriptRow[] }) {
  const track = useRef<HTMLDivElement>(null);
  const rowAt = useEffectEvent((index: number) => rows[index % rows.length]);
  const count = rows.length;

  useEffect(() => {
    const element = track.current;
    if (element === null || count === 0) return;
    const random = seededRandom(31337);
    let index = 0;
    let clock = Math.floor(180 + random() * 120);
    const next = () => {
      const row = rowAt(index);
      index += 1;
      clock += 8 + Math.floor(random() * 32);
      return row === undefined ? document.createElement("div") : rowElement(row, clock);
    };
    // Экран ленты и по строке в запас сверху и снизу: край закрыт в момент подмены строки.
    for (let shown = 0; shown < 6; shown += 1) element.appendChild(next());
    if (prefersReducedMotion()) return () => element.replaceChildren();

    let frame = 0;
    let previous = 0;
    let offset = 0;
    const step = (now: number) => {
      offset += (SPEED * (now - (previous || now))) / 1000;
      previous = now;
      // Высота строки задана в cqi и меняется с шириной колонки: берётся с живого узла.
      const height = element.firstElementChild?.getBoundingClientRect().height ?? 0;
      while (height > 0 && offset >= height) {
        offset -= height;
        element.firstElementChild?.remove();
        element.appendChild(next());
      }
      element.style.transform = `translate3d(0, ${-offset}px, 0)`;
      frame = window.requestAnimationFrame(step);
    };
    frame = window.requestAnimationFrame(step);
    return () => {
      window.cancelAnimationFrame(frame);
      element.replaceChildren();
    };
  }, [count]);

  return (
    <div className="mask-[linear-gradient(to_bottom,transparent,black_12%,black_88%,transparent)] relative mt-[1.2cqi] h-[calc(var(--transcript-row)*4)] overflow-hidden [--transcript-row:clamp(30px,4.7cqi,56px)]">
      <div ref={track} className="absolute inset-x-0 top-0" />
    </div>
  );
}
