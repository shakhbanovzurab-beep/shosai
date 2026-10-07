import type { ReactNode } from "react";

import { TrendingDown, TrendingUp } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";

import { change, formatChange } from "../domain/format";

/** Whether a rise is good news (revenue) or bad news (churn, refunds). */
export type Polarity = "up-good" | "up-bad";

const GOOD =
  "border-green-200 bg-green-500/10 text-green-700 dark:border-green-900/40 dark:bg-green-500/15 dark:text-green-300";
const BAD = "border-destructive/20 bg-destructive/10 text-destructive";

export function Trend({ delta, label, polarity }: { delta: number; label: string; polarity: Polarity }) {
  if (delta === 0) return <Badge variant="outline">{label}</Badge>;
  const up = delta > 0;
  const good = up === (polarity === "up-good");
  const Icon = up ? TrendingUp : TrendingDown;
  return (
    <Badge variant="outline" className={good ? GOOD : BAD}>
      <Icon aria-hidden="true" />
      <span className="sr-only">{up ? "рост" : "снижение"}</span>
      {label}
    </Badge>
  );
}

/** A relative change badge, or nothing when there is no previous value to compare with. */
export function RelativeTrend({
  current,
  previous,
  polarity,
}: {
  current: number;
  previous: number;
  polarity: Polarity;
}) {
  const ratio = change(current, previous);
  return ratio === null ? null : <Trend delta={ratio} label={formatChange(ratio)} polarity={polarity} />;
}

export const Strong = ({ children }: { children: ReactNode }) => (
  <span className="font-medium text-foreground tabular-nums">{children}</span>
);

export function Kpi({
  title,
  value,
  trend,
  footnote,
}: {
  title: string;
  value: string;
  trend?: ReactNode;
  footnote: ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <CardDescription>{title}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-3xl tabular-nums leading-none tracking-tight">{value}</span>
          {trend}
        </div>
        <p className="text-muted-foreground text-sm">{footnote}</p>
      </CardContent>
    </Card>
  );
}
