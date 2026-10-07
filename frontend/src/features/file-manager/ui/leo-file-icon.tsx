import type { SVGProps } from "react";

import { cn } from "cn";

/**
 * A file Leo reads: a sheet with Leo's orb on its corner. Drawn on Lucide's 24px grid with its 2px
 * round stroke, so it sits next to the other icons and stays readable at 14px.
 */
export function LeoFileIcon({ className, ...props }: SVGProps<SVGSVGElement>) {
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
      <path d="M12 21H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h8l4 4v4" />
      <path d="M14 3v4h4" />
      <path d="M8 12h4" />
      <circle cx="18" cy="17.5" r="3.5" />
    </svg>
  );
}
