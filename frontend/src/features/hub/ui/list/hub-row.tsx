import { CircleCheck } from "lucide-react";
import { useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";
import { Link } from "@/lib/navigation";

import type { Hub } from "../../domain/contract";
import { hubPath } from "../../domain/paths";
import type { HubDialogKind } from "../dialogs/hub-dialogs";
import { HubMenu } from "../dialogs/hub-menu";
import { BoardLine } from "../hub/hub-header";
import { useHubPhrases } from "../shared/phrases";
import { GapIcon } from "../shared/urgency";

/**
 * A hub in the list, from its own summary (no request per row): its name, the most urgent gap in one
 * phrase, how many topics are open, where its work goes, and its rhythm, said quietly.
 */
export function HubRow({ hub, onAction }: { hub: Hub; onAction: (kind: HubDialogKind, hub: Hub) => void }) {
  const t = useTranslations("hub");
  const say = useHubPhrases();
  return (
    <li className="relative flex items-start gap-3 px-4 py-3.5 first:rounded-t-xl last:rounded-b-xl hover:bg-muted/40 has-[a[data-hub-link]:focus-visible]:bg-muted/40">
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
          <Link
            href={hubPath(hub.id)}
            data-hub-link=""
            dir="auto"
            className="min-w-0 truncate font-medium outline-none after:absolute after:inset-0 after:rounded-[inherit] after:content-[''] focus-visible:after:ring-3 focus-visible:after:ring-ring/50"
          >
            {hub.name}
          </Link>
          {hub.archived ? <Badge variant="secondary">{t("list.archived")}</Badge> : null}
        </div>
        <p className="flex items-start gap-1.5 text-sm">
          {hub.topGap ? (
            <>
              <GapIcon kind={hub.topGap.kind} className="mt-0.5" />
              <span>{say.gap(hub.topGap)}</span>
            </>
          ) : (
            <>
              <CircleCheck className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
              <span className="text-muted-foreground">{t("list.allClosed")}</span>
            </>
          )}
        </p>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-muted-foreground text-xs">
          <span className="relative z-10 min-w-0">
            <BoardLine hub={hub} />
          </span>
          {hub.rhythmDays === null ? null : <span>{say.rhythm(hub.rhythmDays)}</span>}
        </div>
      </div>
      <div className="relative z-10 flex shrink-0 items-center gap-1">
        {hub.openThreads > 0 ? (
          <span className="text-muted-foreground text-sm tabular-nums">
            {t("list.openCount", { count: hub.openThreads })}
          </span>
        ) : null}
        <HubMenu hub={hub} onAction={onAction} withOpen className="border-transparent bg-transparent" />
      </div>
    </li>
  );
}
