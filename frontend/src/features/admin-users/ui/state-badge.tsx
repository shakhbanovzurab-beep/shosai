import { Badge } from "@/components/ui/badge";

import type { AccountState } from "../domain/contract";
import { STATE_LABEL } from "../domain/labels";

// Цвет — только там, где нужно внимание; подпись всегда словами.
const STYLE: Partial<Record<AccountState, string>> = {
  frozen: "bg-amber-500/10 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  banned: "bg-red-500/10 text-red-700 dark:bg-red-500/15 dark:text-red-300",
  deletion_scheduled: "bg-red-500/10 text-red-700 dark:bg-red-500/15 dark:text-red-300",
};

export function StateBadge({ state }: { state: AccountState }) {
  const style = STYLE[state];
  return style ? (
    <Badge className={style}>{STATE_LABEL[state]}</Badge>
  ) : (
    <Badge variant="outline">{STATE_LABEL[state]}</Badge>
  );
}
