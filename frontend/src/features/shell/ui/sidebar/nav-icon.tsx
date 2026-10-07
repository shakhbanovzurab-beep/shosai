import type { LucideIcon } from "lucide-react";

/** A nav item's icon: muted at rest, full strength when the item is hovered or active. */
export function NavIcon({ icon: Icon, title }: { icon?: LucideIcon; title: string }) {
  if (Icon) {
    return (
      <Icon
        className="text-sidebar-foreground/60 transition-colors group-hover/menu-button:text-sidebar-foreground group-data-[active=true]/menu-button:text-sidebar-foreground"
        aria-hidden="true"
      />
    );
  }
  return (
    <span
      className="flex size-4 shrink-0 items-center justify-center rounded-xs font-medium text-[10px] outline"
      aria-hidden="true"
    >
      {title.slice(0, 1)}
    </span>
  );
}

/** Active rows get a short primary bar at the left edge, on top of the sidebar's soft active background. */
export const navButtonClass =
  "relative before:absolute before:top-1/2 before:start-0 before:h-4 before:w-0.5 before:-translate-y-1/2 before:rounded-full before:bg-primary before:opacity-0 before:transition-opacity data-[active=true]:before:opacity-100";
