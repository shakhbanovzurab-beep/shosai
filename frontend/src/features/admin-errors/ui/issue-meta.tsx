import { cn } from "cn";
import { CircleX, Globe, Grid2x2, type LucideIcon, OctagonAlert, TriangleAlert } from "lucide-react";
import { siApple } from "simple-icons";

import { SimpleIcon } from "@/components/simple-icon";
import { Badge } from "@/components/ui/badge";

import type { ErrorSeverity, ErrorSource, IssueStatus, PlatformComponent } from "../domain/dimensions";
import { COMPONENT_LABEL, SEVERITY_LABEL, SOURCE_LABEL, STATUS_LABEL } from "../domain/labels";
import { STATUS_ICON } from "./status-icons";

/** Severity is the one place with color, always next to its icon and label. */
const SEVERITY_STYLE: Record<ErrorSeverity, { icon: LucideIcon; className: string }> = {
  critical: {
    icon: OctagonAlert,
    className: "bg-red-500/10 text-red-700 dark:bg-red-500/15 dark:text-red-300",
  },
  error: {
    icon: CircleX,
    className: "bg-orange-500/10 text-orange-700 dark:bg-orange-500/15 dark:text-orange-300",
  },
  warning: {
    icon: TriangleAlert,
    className: "bg-amber-500/10 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  },
};

export function SeverityBadge({ severity }: { severity: ErrorSeverity }) {
  const { icon: Icon, className } = SEVERITY_STYLE[severity];
  return (
    <Badge className={className}>
      <Icon aria-hidden="true" />
      {SEVERITY_LABEL[severity]}
    </Badge>
  );
}

export function StatusBadge({ status }: { status: IssueStatus }) {
  const Icon = STATUS_ICON[status];
  return (
    <Badge variant="outline" className={cn(status === "ignored" && "text-muted-foreground")}>
      <Icon aria-hidden="true" />
      {STATUS_LABEL[status]}
    </Badge>
  );
}

/** OS mark of a source. simple-icons has no Windows mark, so it uses a neutral four-pane glyph. */
export function SourceIcon({ source, className }: { source: ErrorSource; className?: string }) {
  if (source === "macos") return <SimpleIcon icon={siApple} className={cn("size-4", className)} aria-hidden="true" />;
  const Glyph = source === "windows" ? Grid2x2 : Globe;
  return <Glyph className={cn("size-4", className)} aria-hidden="true" />;
}

export function SourceLabel({ source, component }: { source: ErrorSource; component: PlatformComponent | null }) {
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
      <SourceIcon source={source} className="text-muted-foreground" />
      <span>{SOURCE_LABEL[source]}</span>
      {component ? <span className="text-muted-foreground">· {COMPONENT_LABEL[component]}</span> : null}
    </span>
  );
}
