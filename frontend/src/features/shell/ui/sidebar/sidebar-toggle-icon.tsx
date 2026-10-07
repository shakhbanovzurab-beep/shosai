import { cn } from "cn";

type SidebarToggleIconProps = {
  /** Which way the arrow points when it shows: "close" ‹ collapses the sidebar, "open" › expands it. */
  direction: "close" | "open";
  /** Classes that reveal the arrow, e.g. `group-hover/toggle:opacity-100`; omit to always show it. */
  revealClassName?: string;
  className?: string;
};

/**
 * Our sidebar toggle glyph: a rounded panel with a divider. On hover a small arrow slides in next to
 * the divider, pointing the way the sidebar will move. Inherits colour and size from its parent.
 * Mirrored right to left, where the sidebar is on the right.
 */
export function SidebarToggleIcon({ direction, revealClassName, className }: SidebarToggleIconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={cn("size-5 shrink-0 rtl:-scale-x-100", className)}
      aria-hidden="true"
    >
      <rect x="3" y="3" width="18" height="18" rx="5" />
      <path d="M8.5 8v8" />
      <path
        d={direction === "close" ? "M15.75 9l-3 3 3 3" : "M13.5 9l3 3-3 3"}
        className={cn(
          "transition-[opacity,transform] duration-200 ease-out motion-reduce:transition-none",
          revealClassName
            ? cn("opacity-0", direction === "close" ? "translate-x-0.5" : "-translate-x-0.5", revealClassName)
            : undefined,
        )}
      />
    </svg>
  );
}
