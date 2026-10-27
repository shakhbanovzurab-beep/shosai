import { cn } from "cn";
import type { LucideIcon } from "lucide-react";
import { CircleCheck, CircleDot, CircleX, Loader, TriangleAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";

import type { LiveKitEgressStatus, LiveKitHealth, LiveKitNodeState } from "../domain/contract";

type Tone = "good" | "warning" | "critical" | "info" | "neutral";

const TONES: Record<Tone, string> = {
  good: "bg-green-500/10 text-green-700 dark:bg-green-500/15 dark:text-green-300",
  warning: "bg-amber-500/10 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  critical: "bg-red-500/10 text-red-700 dark:bg-red-500/15 dark:text-red-300",
  info: "bg-sky-500/10 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300",
  neutral: "bg-muted text-muted-foreground",
};

type Status = { label: string; tone: Tone; icon: LucideIcon };

/** A state shown with an icon and a word, never by color alone. */
function StatusBadge({ status, className }: { status: Status; className?: string }) {
  const Icon = status.icon;
  return (
    <Badge className={cn(TONES[status.tone], className)}>
      <Icon aria-hidden="true" />
      {status.label}
    </Badge>
  );
}

const HEALTH: Record<LiveKitHealth, Status> = {
  healthy: { label: "Работает", tone: "good", icon: CircleCheck },
  degraded: { label: "Деградация", tone: "warning", icon: TriangleAlert },
  down: { label: "Недоступен", tone: "critical", icon: CircleX },
};

const NODE_STATE: Record<LiveKitNodeState, Status> = {
  serving: { label: "Работает", tone: "good", icon: CircleCheck },
  down: { label: "Недоступен", tone: "critical", icon: CircleX },
};

const EGRESS: Record<LiveKitEgressStatus, Status> = {
  starting: { label: "Запускается", tone: "info", icon: Loader },
  active: { label: "Идёт запись", tone: "info", icon: CircleDot },
  ending: { label: "Завершается", tone: "info", icon: Loader },
  complete: { label: "Готово", tone: "good", icon: CircleCheck },
  failed: { label: "Ошибка", tone: "critical", icon: CircleX },
};

export const HealthBadge = ({ health }: { health: LiveKitHealth }) => <StatusBadge status={HEALTH[health]} />;
export const NodeStateBadge = ({ state }: { state: LiveKitNodeState }) => <StatusBadge status={NODE_STATE[state]} />;
export const EgressBadge = ({ status }: { status: LiveKitEgressStatus }) => <StatusBadge status={EGRESS[status]} />;
