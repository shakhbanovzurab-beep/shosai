import type { ReactNode } from "react";

import { cn } from "cn";

const RADIUS = 45;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/**
 * The phase as a ring that fills up: primary while focusing, green on a break. It fills clockwise from the top
 * in every language, like a clock face, so right to left doesn't mirror it.
 */
export function FocusRing({
  progress,
  onBreak,
  children,
}: {
  progress: number;
  onBreak: boolean;
  children: ReactNode;
}) {
  return (
    <div className="relative grid size-44 place-items-center">
      <svg viewBox="0 0 100 100" className="absolute inset-0 -rotate-90" aria-hidden="true">
        <circle cx="50" cy="50" r={RADIUS} fill="none" strokeWidth="5" className="stroke-muted" />
        <circle
          cx="50"
          cy="50"
          r={RADIUS}
          fill="none"
          strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={CIRCUMFERENCE * (1 - Math.min(1, Math.max(0, progress)))}
          className={cn(
            "transition-[stroke-dashoffset] duration-1000 ease-linear motion-reduce:transition-none",
            onBreak ? "stroke-emerald-500" : "stroke-primary",
          )}
        />
      </svg>
      <div className="relative flex flex-col items-center gap-1">{children}</div>
    </div>
  );
}
