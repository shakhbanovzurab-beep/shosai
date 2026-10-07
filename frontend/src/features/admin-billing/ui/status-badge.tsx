import { cn } from "cn";

import { Badge } from "@/components/ui/badge";

import type { TransactionStatus } from "../domain/contract";
import { STATUS_LABELS } from "../domain/labels";
import { STATUS_STYLES } from "./status-styles";

export function StatusBadge({ status, className }: { status: TransactionStatus; className?: string }) {
  const { icon: Icon, badge } = STATUS_STYLES[status];
  return (
    <Badge variant="outline" className={cn(badge, className)}>
      <Icon aria-hidden="true" />
      {STATUS_LABELS[status]}
    </Badge>
  );
}
