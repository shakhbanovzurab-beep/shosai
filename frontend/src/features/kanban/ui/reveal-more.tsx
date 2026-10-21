"use client";

import { useEffect, useRef } from "react";

/**
 * Невидимая отметка в конце показанной части колонки: когда она подходит к краю экрана, колонка показывает
 * следующие карточки. Так длинная колонка держит в DOM столько карточек, сколько человек долистал, и
 * перетаскивание не меряет сотни скрытых.
 */
export function RevealMore({ onReveal }: { onReveal: () => void }) {
  const marker = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = marker.current;
    if (!element) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) onReveal();
      },
      { rootMargin: "0px 0px 400px 0px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [onReveal]);
  return <div ref={marker} aria-hidden="true" className="h-px shrink-0" />;
}
