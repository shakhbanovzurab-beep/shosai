import { cn } from "cn";

import { ShosaiMark } from "@/components/shosai-mark";

/** The workspace's mark: its first letter on the primary colour, like an app icon. */
export function WorkspaceTile({ name, className }: { name: string; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "grid size-5 shrink-0 place-items-center rounded-md bg-primary font-semibold text-[11px] text-primary-foreground uppercase",
        className,
      )}
    >
      {name.trim().slice(0, 1) || "W"}
    </span>
  );
}

/** The personal scope's mark: the app's own logo, a little larger than a workspace tile, so it reads as the brand. */
export function PersonalTile({ className }: { className?: string }) {
  return <ShosaiMark className={cn("size-6!", className)} />;
}
