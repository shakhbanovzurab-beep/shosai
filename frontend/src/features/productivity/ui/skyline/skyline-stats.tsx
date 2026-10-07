import type * as React from "react";

import { cn } from "cn";

import { useDirection } from "@/components/ui/direction";

import type { StatView } from "./skyline-stat-views";

const EASE = "cubic-bezier(0.65, 0, 0.35, 1)";

function Stat({ label, value, unit, sub, size, align }: StatView & { size: number; align: "start" | "end" }) {
  return (
    <div className="grid grid-cols-[auto_auto] items-end gap-x-2" style={{ justifyContent: align }}>
      {align === "end" ? (
        <>
          <div className="text-end text-muted-foreground text-xs leading-tight">{label}</div>
          <div />
        </>
      ) : (
        <div className="col-span-2 text-muted-foreground text-xs leading-tight">{label}</div>
      )}
      <div
        className="text-end font-semibold text-primary tabular-nums tracking-tight"
        style={{ fontSize: size, lineHeight: 0.95 }}
      >
        {value}
      </div>
      <div className="pb-[0.15em] leading-tight">
        <div className="text-sm">{unit}</div>
        <div className="whitespace-nowrap text-muted-foreground text-xs">{sub}</div>
      </div>
    </div>
  );
}

/**
 * Two pairs of big numbers that settle into the empty corners of the 3D skyline. The drawing runs left to right
 * in every language (see contribution-skyline.tsx), so its empty corners are always the top right and the bottom
 * left: the blocks sit there in the chart's frame, and inside them the words follow the page direction, each
 * block hugging its corner.
 */
export function SkylineCornerStats({
  stats,
  visible,
  size,
  duration,
}: {
  stats: StatView[];
  visible: boolean;
  size: number;
  duration: number;
}) {
  const dir = useDirection();
  // Each block hugs its corner: the right-hand side is the end left to right, the start right to left.
  const toRight = dir === "rtl" ? "start" : "end";
  const toLeft = dir === "rtl" ? "end" : "start";
  const corner = (delay: number, shift: number): React.CSSProperties => ({
    opacity: visible ? 1 : 0,
    transform: visible ? "translateY(0)" : `translateY(${shift}px)`,
    transitionDuration: visible ? "600ms" : "300ms",
    transitionDelay: visible ? `${Math.round(duration * delay)}ms` : "0ms",
    transitionTimingFunction: EASE,
  });
  const base = "pointer-events-none absolute transition-[opacity,transform] motion-reduce:transition-none";
  const column = (align: "start" | "end") => cn("flex flex-col gap-5", align === "end" ? "items-end" : "items-start");
  return (
    <>
      <div aria-hidden={!visible} className={cn(base, "end-1 top-1")} style={corner(0.55, -10)}>
        <div dir={dir} className={column(toRight)}>
          <Stat {...stats[0]} size={size} align={toRight} />
          <Stat {...stats[1]} size={size} align={toRight} />
        </div>
      </div>
      <div aria-hidden={!visible} className={cn(base, "start-1 bottom-1")} style={corner(0.65, 10)}>
        <div dir={dir} className={column(toLeft)}>
          <Stat {...stats[2]} size={size} align={toLeft} />
          <Stat {...stats[3]} size={size} align={toLeft} />
        </div>
      </div>
    </>
  );
}

/** The same four numbers as a compact row, for the flat view and narrow cards. */
export function SkylineStatsRow({ stats }: { stats: StatView[] }) {
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-3 border-t px-3 py-3 sm:grid-cols-4 sm:px-4">
      {stats.map((s) => (
        <div key={s.id} className="min-w-0">
          <dt className="text-muted-foreground text-xs leading-tight">{s.label}</dt>
          <dd className="mt-1 flex items-baseline gap-1.5">
            <span className="font-semibold text-2xl text-primary tabular-nums leading-none tracking-tight">
              {s.value}
            </span>
            <span className="text-sm">{s.unit}</span>
          </dd>
          <dd className="mt-0.5 truncate text-muted-foreground text-xs">{s.sub}</dd>
        </div>
      ))}
    </dl>
  );
}
