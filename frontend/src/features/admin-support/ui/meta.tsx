import { cn } from "cn";
import type { LucideIcon } from "lucide-react";
import { Globe, Laptop, Monitor } from "lucide-react";

import type { ConversationPriority, SupportChannel } from "../domain/contract";
import { CHANNEL_LABELS, PRIORITY_LABELS } from "../domain/labels";

const CHANNEL_ICONS: Record<SupportChannel, LucideIcon> = { web: Globe, macos: Laptop, windows: Monitor };

/** Named palette colours for the priority signal: theme tokens have no amber/orange scale. */
const PRIORITY_DOT: Record<ConversationPriority, string> = {
  low: "bg-muted-foreground/40",
  normal: "bg-sky-500",
  high: "bg-amber-500",
  urgent: "bg-destructive",
};

export function ChannelLabel({ channel }: { channel: SupportChannel }) {
  const Icon = CHANNEL_ICONS[channel];
  return (
    <span className="inline-flex items-center gap-1">
      <Icon className="size-3.5" aria-hidden="true" />
      {CHANNEL_LABELS[channel]}
    </span>
  );
}

export function PriorityLabel({ priority }: { priority: ConversationPriority }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={cn("size-2 shrink-0 rounded-full", PRIORITY_DOT[priority])} aria-hidden="true" />
      {PRIORITY_LABELS[priority]}
    </span>
  );
}
