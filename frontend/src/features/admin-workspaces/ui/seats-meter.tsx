import { cn } from "cn";

import { formatNumber } from "../domain/format";

/** "12 / 18" with a thin bar; amber once the seats run out, so the next invitation would be refused. */
export function SeatsMeter({ used, seats, className }: { used: number; seats: number; className?: string }) {
  const share = seats > 0 ? Math.min(1, used / seats) : 1;
  const full = used >= seats;
  return (
    <div className={cn("flex w-28 flex-col gap-1", className)}>
      <span className="text-sm tabular-nums">
        {formatNumber(used)} / {formatNumber(seats)}
        {full ? <span className="sr-only"> — свободных мест нет</span> : null}
      </span>
      <span className="h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden="true">
        <span
          className={cn("block h-full rounded-full", full ? "bg-amber-500" : "bg-primary")}
          style={{ width: `${Math.round(share * 100)}%` }}
        />
      </span>
    </div>
  );
}
