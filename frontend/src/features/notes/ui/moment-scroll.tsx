"use client";

import { useEffect } from "react";

/** Brings the transcript line a link pointed at (`?t=` seconds) into view once the page is shown. */
export function MomentScroll() {
  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    document
      .getElementById("transcript-moment")
      ?.scrollIntoView({ block: "center", behavior: reduce ? "auto" : "smooth" });
  }, []);
  return null;
}
