import type { ReactNode } from "react";

import type { LucideIcon } from "lucide-react";

import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";

/** An empty or filtered-out state: what is missing, how it gets filled, and the one action that helps. */
export function EmptyMessage({
  icon: Icon,
  title,
  text,
  action,
}: {
  icon: LucideIcon;
  title: string;
  text: ReactNode;
  action?: ReactNode;
}) {
  return (
    <Empty className="rounded-xl border border-dashed">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <Icon />
        </EmptyMedia>
        <EmptyTitle>{title}</EmptyTitle>
        <EmptyDescription>{text}</EmptyDescription>
      </EmptyHeader>
      {action ? <EmptyContent className="flex-row flex-wrap justify-center gap-2">{action}</EmptyContent> : null}
    </Empty>
  );
}
