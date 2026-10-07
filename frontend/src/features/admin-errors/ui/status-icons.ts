import { CircleCheck, CircleDashed, CircleDot, EyeOff, type LucideIcon } from "lucide-react";

import type { IssueStatus } from "../domain/dimensions";

/** Icons of issue statuses, shared by the badge and the status picker. */
export const STATUS_ICON: Record<IssueStatus, LucideIcon> = {
  new: CircleDot,
  in_progress: CircleDashed,
  resolved: CircleCheck,
  ignored: EyeOff,
};
