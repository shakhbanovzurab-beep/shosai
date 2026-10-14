import { type RefObject, useEffect, useEffectEvent } from "react";

import { prefersReducedMotion, seededRandom } from "./poster-script";

/** Одновременно живущих реплик; если свободной реплики нет, место ждёт — одна фраза дважды читается повтором. */
const SLOTS = 20;
const FRAGMENT_CLASS = "absolute whitespace-nowrap font-bold font-mono text-foreground opacity-0";

/**
 * Поле сумбура: каждая реплика живёт своим сроком и возвращается уже другой и в другом месте, поэтому у поля
 * нет периода. Анимация императивная (WAAPI на узлах), а не через состояние React: декорация не перерисовывает
 * дерево. Реплики берутся из `lines` в момент появления — смена языка подхватывается без перезапуска.
 */
export function useChaosField(
  host: RefObject<HTMLDivElement | null>,
  lines: readonly string[],
  onHeard: (line: string) => void,
) {
  const lineAt = useEffectEvent((index: number) => lines[index % lines.length] ?? "");
  const heard = useEffectEvent((line: string) => onHeard(line));
  const count = lines.length;

  useEffect(() => {
    const box = host.current;
    if (box === null || count === 0) return;
    const random = seededRandom(20260829);
    const reduced = prefersReducedMotion();
    const timers: number[] = [];
    const busy = new Set<number>();
    const nodes: HTMLDivElement[] = [];

    const freeLine = () => {
      const from = Math.floor(random() * count);
      for (let step = 0; step < count; step += 1) {
        const index = (from + step) % count;
        if (!busy.has(index)) return index;
      }
      return -1;
    };

    for (let slot = 0; slot < SLOTS; slot += 1) {
      const node = document.createElement("div");
      node.className = FRAGMENT_CLASS;
      box.appendChild(node);
      nodes.push(node);

      // Ставит свободную реплику в случайное место; возвращает её пиковую прозрачность или null, если ждать.
      const place = (): { index: number; peak: number } | null => {
        const index = freeLine();
        if (index < 0) return null;
        busy.add(index);
        node.textContent = lineAt(index);
        node.style.fontSize = `clamp(10px, ${(1.28 + random() * 0.75).toFixed(2)}cqi, 22px)`;
        node.style.insetInlineStart = `${(-8 + random() * 96).toFixed(1)}%`;
        node.style.top = `${(random() * 88).toFixed(1)}%`;
        node.style.rotate = `${(-4 + random() * 8).toFixed(1)}deg`;
        return { index, peak: 0.18 + random() * 0.62 };
      };

      if (reduced) {
        const still = place();
        if (still !== null) node.style.opacity = String(still.peak);
        continue;
      }

      const live = () => {
        const placed = place();
        if (placed === null) {
          timers.push(window.setTimeout(live, 400 + random() * 900));
          return;
        }
        heard(node.textContent ?? "");
        const fadeIn = 500 + random() * 500;
        const hold = 2400 + random() * 4600;
        const total = fadeIn + hold + 600 + random() * 800;
        const { peak } = placed;
        const animation = node.animate(
          [
            { opacity: 0 },
            { opacity: peak, offset: fadeIn / total },
            { opacity: peak, offset: (fadeIn + hold) / total },
            { opacity: 0 },
          ],
          { duration: total, easing: "linear" },
        );
        animation.onfinish = () => {
          busy.delete(placed.index);
          timers.push(window.setTimeout(live, 150 + random() * 1800));
        };
      };
      timers.push(window.setTimeout(live, slot * 150 + random() * 2600));
    }

    return () => {
      for (const timer of timers) window.clearTimeout(timer);
      for (const node of nodes) {
        for (const animation of node.getAnimations()) animation.cancel();
        node.remove();
      }
    };
  }, [host, count]);
}
