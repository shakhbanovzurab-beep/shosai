"use client";

import { useState } from "react";

import { useTranslations } from "next-intl";

import { ConfirmDestructive, LoadError } from "@/components/feedback";
import { Skeleton } from "@/components/ui/skeleton";

import { CONNECTORS, type ConnectorDefinition } from "../domain/connectors";
import type { Connector } from "../domain/contract";
import { disconnectSource } from "../model/connector-actions";
import { connectorsResource, useConnectors } from "../model/kb-resources";
import { ConnectorCard } from "./connector-card";
import { ConnectorDialog } from "./connector-dialog";
import { useConnectorName } from "./connector-name";

/** Every source Leo can sync from, with its status and actions. */
export function SourcesTab() {
  const t = useTranslations("knowledgeBaseSources");
  const nameOf = useConnectorName();
  const state = useConnectors();
  const [configuring, setConfiguring] = useState<ConnectorDefinition | null>(null);
  const [disconnecting, setDisconnecting] = useState<ConnectorDefinition | null>(null);

  if (state.status === "error") {
    return (
      <LoadError title={t("loadFailed")} message={state.message} onRetry={() => void connectorsResource.refresh()} />
    );
  }

  const byId = new Map<string, Connector>(state.status === "ready" ? state.data.connectors.map((c) => [c.id, c]) : []);
  const connected = CONNECTORS.filter((d) => (byId.get(d.id)?.status ?? "disconnected") !== "disconnected").length;

  return (
    <div className="flex flex-col gap-4">
      <p className="text-muted-foreground text-sm">
        {state.status === "ready" ? t("connectedCount", { connected, total: CONNECTORS.length }) : t("loading")}
      </p>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
        {CONNECTORS.map((definition) => {
          const connector = byId.get(definition.id);
          return connector ? (
            <ConnectorCard
              key={definition.id}
              definition={definition}
              connector={connector}
              onConfigure={() => setConfiguring(definition)}
              onDisconnect={() => setDisconnecting(definition)}
            />
          ) : (
            <Skeleton key={definition.id} className="h-48 rounded-xl" />
          );
        })}
      </div>

      <ConnectorDialog
        key={configuring?.id ?? "none"}
        definition={configuring}
        connector={configuring ? (byId.get(configuring.id) ?? null) : null}
        onClose={() => setConfiguring(null)}
      />

      <ConfirmDestructive
        open={disconnecting !== null}
        title={t("disconnect.title", { name: disconnecting ? nameOf(disconnecting) : "" })}
        description={t("disconnect.description")}
        confirmLabel={t("disconnect.confirm")}
        onConfirm={() => disconnecting && void disconnectSource(disconnecting, nameOf(disconnecting), t)}
        onCancel={() => setDisconnecting(null)}
      />
    </div>
  );
}
