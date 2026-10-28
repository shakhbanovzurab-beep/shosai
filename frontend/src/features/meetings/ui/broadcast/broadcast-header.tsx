import { useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";

import type { BroadcastSnapshot } from "../../domain/broadcast";

/** Шапка трансляции: название, в эфире ли она и сколько зрителей; неизвестное число зрителей — не ноль. */
export function BroadcastHeader({ broadcast }: { broadcast: BroadcastSnapshot }) {
  const t = useTranslations("meetingBroadcast");
  const live = broadcast.status === "live";
  return (
    <header className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2">
      <h1 dir="auto" className="truncate font-medium">
        {broadcast.title}
      </h1>
      <Badge variant={live ? "destructive" : "secondary"}>
        {live ? <span aria-hidden="true" className="size-1.5 rounded-full bg-current" /> : null}
        {t(`status.${broadcast.status}`)}
      </Badge>
      {live ? (
        <span className="ms-auto text-muted-foreground text-sm tabular-nums">
          {broadcast.viewers === null ? t("viewersUnknown") : t("viewers", { count: broadcast.viewers })}
        </span>
      ) : null}
    </header>
  );
}
