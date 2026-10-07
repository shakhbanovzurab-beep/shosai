"use client";

import * as React from "react";

/**
 * Lets a vertical mouse wheel scroll the pill row sideways, but only while the row can still move that way.
 * Wheeling down moves towards the end of the row, which is to the left in a right-to-left layout.
 */
export function useHorizontalWheel(ref: React.RefObject<HTMLDivElement | null>) {
  React.useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const onWheel = (event: WheelEvent) => {
      if (Math.abs(event.deltaX) > Math.abs(event.deltaY)) return;
      // Right to left, scrollLeft runs from 0 at the start down to minus the overflow at the end.
      const towardsEnd = getComputedStyle(element).direction === "rtl" ? -1 : 1;
      const maxScroll = element.scrollWidth - element.clientWidth;
      const travelled = element.scrollLeft * towardsEnd;
      const canScroll = event.deltaY < 0 ? travelled > 0 : travelled < maxScroll;
      if (maxScroll <= 0 || !canScroll) return;
      event.preventDefault();
      element.scrollLeft += event.deltaY * towardsEnd;
    };
    element.addEventListener("wheel", onWheel, { passive: false });
    return () => element.removeEventListener("wheel", onWheel);
  }, [ref]);
}
