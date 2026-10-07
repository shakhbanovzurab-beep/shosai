import { cn } from "cn";
import { Command } from "lucide-react";

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

/** The personal scope's mark: the app's own logo. */
export function PersonalTile({ className }: { className?: string }) {
  return <Command aria-hidden="true" className={cn("size-4 shrink-0", className)} />;
}
