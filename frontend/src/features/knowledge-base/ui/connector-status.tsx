"use client";

import { CircleAlert, CircleCheck } from "lucide-react";
import { useFormatter, useNow, useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";

import { BUSY_CONNECTOR, type Connector } from "../domain/contract";

function StatusBadge({ connector }: { connector: Connector }) {
  const t = useTranslations("knowledgeBaseSources");
  if (BUSY_CONNECTOR.has(connector.status)) {
    return (
      <Badge variant="secondary" className="gap-1 rounded-md">
        <Spinner className="size-3" />
        {connector.status === "connecting" ? t("status.connecting") : t("status.syncing")}
      </Badge>
    );
  }
  if (connector.status === "connected") {
    return (
      <Badge variant="secondary" className="gap-1 rounded-md">
        <CircleCheck className="text-emerald-600 dark:text-emerald-400" />
        {t("status.connected")}
      </Badge>
    );
  }
  if (connector.status === "error") {
    return (
      <Badge variant="destructive" className="gap-1 rounded-md">
        <CircleAlert />
        {t("status.error")}
      </Badge>
    );
  }
  return null;
}

/** "Synced 5 minutes ago", brought up to date once a minute. Connectors load in the browser, never during SSR. */
function SyncedAgo({ at }: { at: string }) {
  const t = useTranslations("knowledgeBaseSources");
  const format = useFormatter();
  const now = useNow({ updateInterval: 60_000 });
  const synced = new Date(Math.min(Date.parse(at), now.getTime()));
  return <span>{t("card.synced", { ago: format.relativeTime(synced, now) })}</span>;
}

/** Status, item count and last sync for a linked source. */
export function ConnectorDetails({ connector }: { connector: Connector }) {
  const t = useTranslations("knowledgeBaseSources");
  const settled = connector.status === "connected";
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-muted-foreground text-sm">
      <StatusBadge connector={connector} />
      {connector.error ? (
        <span className="text-destructive" dir="auto">
          {connector.error}
        </span>
      ) : null}
      {settled ? <span className="tabular-nums">{t("card.items", { count: connector.items_indexed })}</span> : null}
      {settled && connector.last_synced_at ? <SyncedAgo at={connector.last_synced_at} /> : null}
    </div>
  );
}
