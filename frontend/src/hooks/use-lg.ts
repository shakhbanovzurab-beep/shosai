import * as React from "react";

const LG_BREAKPOINT = 1024;
const LG_QUERY = `(min-width: ${LG_BREAKPOINT}px)`;

function subscribe(onChange: () => void) {
  const mql = window.matchMedia(LG_QUERY);
  mql.addEventListener("change", onChange);
  return () => mql.removeEventListener("change", onChange);
}

const getSnapshot = () => window.matchMedia(LG_QUERY).matches;
const getServerSnapshot = () => false;

export function useIsLg() {
  return React.useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
