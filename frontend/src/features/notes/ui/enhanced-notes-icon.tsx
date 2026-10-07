import type { SVGProps } from "react";

import { cn } from "cn";

/**
 * Enhanced notes: Leo's write-up laid over the user's own notes, a clean sheet in front of the raw one.
 * Drawn on Lucide's 24px grid with its 2px round stroke, so it sits with the other tab icons.
 */
export function EnhancedNotesIcon({ className, ...props }: SVGProps<SVGSVGElement>) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={cn("lucide", className)}
      {...props}
    >
      <path d="M8 7V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-1" />
      <rect x="4" y="7" width="13" height="14" rx="2" />
      <path d="M8 12h5" />
      <path d="M8 16h3" />
    </svg>
  );
}
