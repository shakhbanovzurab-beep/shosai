import { cn } from "cn";
import { siApple } from "simple-icons";

import { SimpleIcon } from "@/components/simple-icon";

import type { DesktopPlatform } from "../domain/contract";

/** The platform's mark. simple-icons has no Microsoft marks, so Windows is drawn as its four panes. */
export function OsIcon({ platform, className }: { platform: DesktopPlatform; className?: string }) {
  if (platform === "macos")
    return <SimpleIcon icon={siApple} aria-hidden="true" className={cn("fill-current", className)} />;
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className={cn("fill-current", className)}>
      <path d="M2 4.2 10 3.1v8.4H2zM11 3l11-1.5v10H11zM2 12.5h8v8.4L2 19.8zM11 12.5h11v10L11 21z" />
    </svg>
  );
}
