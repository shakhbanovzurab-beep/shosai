import { useEffect, useState } from "react";

import { LEO_NOTES, type LeoNoteTime, prefersReducedMotion, seededRandom } from "./poster-script";

/**
 * Какое напоминание Leo сейчас на афише. Leo каждый раз говорит новое: сообщения идут по кругу с разным
 * интервалом, чтобы к ритму нельзя было привыкнуть.
 */
export function useLeoNote(): LeoNoteTime {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    if (prefersReducedMotion()) return;
    const random = seededRandom(4441);
    let timer = 0;
    const tick = () => {
      timer = window.setTimeout(
        () => {
          setIndex((current) => (current + 1) % LEO_NOTES.length);
          tick();
        },
        9000 + random() * 9000,
      );
    };
    tick();
    return () => window.clearTimeout(timer);
  }, []);
  return LEO_NOTES[index] ?? LEO_NOTES[0];
}
