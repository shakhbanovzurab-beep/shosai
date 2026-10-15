import { useEffect, useRef } from "react";

import { prefersReducedMotion, seededRandom } from "./poster-script";

// Полосы в покое и на пике, доля высоты.
const FLOOR = 0.12;
const PEAK = 1;
// Время атаки и спада, мс: голос вспыхивает быстро и гаснет чуть мягче.
const ATTACK_MS = 28;
const RELEASE_MS = 90;
// Средние полосы громче крайних — как у спектра речи.
const BAR_WEIGHT = [0.6, 0.85, 1, 0.82, 0.58];

/**
 * Эквалайзер, похожий на живой голос: речь идёт фразами с короткими паузами, внутри фразы — слоги со своей
 * громкостью, у каждой полосы — своя доля и мелкое дрожание на каждом кадре. Высота меняется через transform, без
 * перерисовки React; `speaking` на элементе-хозяине включает свечение, пока звучит фраза.
 */
export function useVoiceBars(count: number) {
  const bars = useRef<(HTMLElement | null)[]>([]);
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const pill = host.current;
    const nodes = bars.current.slice(0, count).filter((node): node is HTMLElement => node !== null);
    if (nodes.length === 0) return;
    if (prefersReducedMotion()) {
      for (const [index, node] of nodes.entries()) node.style.transform = `scaleY(${0.35 + 0.15 * (index % 2)})`;
      return;
    }
    const random = seededRandom(7331);
    const level = nodes.map(() => FLOOR);
    const target = nodes.map(() => FLOOR);
    let speaking = true;
    let phraseLeft = 1600;
    let syllableLeft = 0;
    let frame = 0;
    let previous = 0;

    const nextSyllable = () => {
      syllableLeft = 70 + random() * 90;
      const loudness = speaking ? 0.6 + random() * 0.4 : 0.04 * random();
      for (const index of nodes.keys()) {
        const weight = BAR_WEIGHT[index] ?? 0.7;
        const jitter = 0.65 + random() * 0.35;
        target[index] = FLOOR + (PEAK - FLOOR) * Math.min(1, loudness * weight * jitter * 1.15);
      }
    };

    const step = (now: number) => {
      const dt = Math.min(64, now - (previous || now));
      previous = now;
      phraseLeft -= dt;
      syllableLeft -= dt;
      if (phraseLeft <= 0) {
        speaking = !speaking;
        phraseLeft = speaking ? 1400 + random() * 3200 : 140 + random() * 520;
        syllableLeft = 0;
        if (pill) pill.dataset.speaking = String(speaking);
      }
      if (syllableLeft <= 0) nextSyllable();
      for (const [index, node] of nodes.entries()) {
        const current = level[index] ?? FLOOR;
        const goal = target[index] ?? FLOOR;
        const tau = goal > current ? ATTACK_MS : RELEASE_MS;
        const next = current + (goal - current) * (1 - Math.exp(-dt / tau));
        level[index] = next;
        // Мелкое дрожание поверх слога: живой голос не стоит на одной высоте ни одного кадра.
        const flutter = speaking ? (random() - 0.5) * 0.08 : 0;
        node.style.transform = `scaleY(${Math.max(FLOOR, Math.min(PEAK, next + flutter)).toFixed(3)})`;
      }
      frame = window.requestAnimationFrame(step);
    };
    if (pill) pill.dataset.speaking = "true";
    frame = window.requestAnimationFrame(step);
    return () => window.cancelAnimationFrame(frame);
    // Число полос — зависимость: другой набор полос пересобирает анимацию целиком (и при горячей замене кода).
  }, [count]);
  return { bars, host };
}
