import { cn } from "cn";
import {
  CalendarOff,
  Clock,
  Gavel,
  GitCompareArrows,
  Hourglass,
  type LucideIcon,
  MessageCircleQuestionMark,
  MessageSquareDashed,
  VolumeX,
} from "lucide-react";

import type { Gap, GapKind } from "../../domain/contract";
import { urgencyTier } from "../../domain/urgency";
import { BAR, INK } from "./urgency-tones";

const ICONS: Record<GapKind, LucideIcon> = {
  contradiction: GitCompareArrows,
  overdue: Hourglass,
  due_soon: Clock,
  forgotten: MessageSquareDashed,
  undated: CalendarOff,
  orphan_decision: Gavel,
  unanswered: MessageCircleQuestionMark,
  silence: VolumeX,
};

/** The bar on a row's starting edge (left, or right in right-to-left languages); a row with nothing missing gets a hairline. */
export function UrgencyBar({ gap, className }: { gap: Gap | null; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "absolute start-0 top-3 bottom-3 rounded-full",
        gap ? BAR[urgencyTier(gap.kind)] : "border-border border-s-2 border-solid",
        className,
      )}
    />
  );
}

/** The gap kind's icon, in its tier's ink; decorative, the words next to it carry the meaning. */
export function GapIcon({ kind, className }: { kind: GapKind; className?: string }) {
  const Icon = ICONS[kind];
  return <Icon aria-hidden="true" className={cn("size-3.5 shrink-0", INK[urgencyTier(kind)], className)} />;
}
