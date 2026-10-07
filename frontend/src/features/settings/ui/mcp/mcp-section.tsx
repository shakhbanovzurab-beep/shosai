"use client";

import { useState } from "react";

import { KeyRound, Plug, Plus, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Switch } from "@/components/ui/switch";
import { usePollingResource } from "@/hooks/use-polling-resource";

import type { McpServer } from "../../domain/mcp-contract";
import { MCP_TRANSPORT_NAMES } from "../../domain/names";
import { removeMcpServer, toggleMcpServer } from "../../model/mcp-actions";
import { mcpResource } from "../../model/settings-resources";
import { SectionState } from "../section-state";
import { McpAddForm } from "./mcp-add-form";

function ServerRow({ server }: { server: McpServer }) {
  const t = useTranslations("settingsMcp");
  const { name } = server;
  return (
    <li className="flex items-center gap-3 py-3">
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="flex items-center gap-2 font-medium text-sm">
          <span dir="auto">{name}</span>
          <Badge variant="outline" className="rounded-md font-normal">
            {MCP_TRANSPORT_NAMES[server.transport].short}
          </Badge>
          {server.has_auth ? <KeyRound className="size-3.5 text-muted-foreground" aria-label={t("hasAuth")} /> : null}
        </span>
        <span dir="auto" className="truncate font-mono text-muted-foreground text-xs">
          {server.url}
        </span>
        <span className="text-muted-foreground text-xs">
          {server.tools === null ? t("notReached") : t("tools", { count: server.tools })}
        </span>
      </div>
      <Switch
        checked={server.enabled}
        onCheckedChange={(enabled) => void toggleMcpServer(server, enabled, t)}
        aria-label={server.enabled ? t("disable", { name }) : t("enable", { name })}
      />
      <Button
        variant="ghost"
        size="icon-sm"
        aria-label={t("remove", { name })}
        onClick={() => void removeMcpServer(server, t)}
      >
        <Trash2 />
      </Button>
    </li>
  );
}

function ServerList({ servers, adding }: { servers: McpServer[]; adding: boolean }) {
  const t = useTranslations("settingsMcp");
  if (servers.length > 0) {
    return (
      <ul className="divide-y">
        {servers.map((server) => (
          <ServerRow key={server.id} server={server} />
        ))}
      </ul>
    );
  }
  // While the add form is open it already explains what to do.
  if (adding) return null;
  return (
    <Empty className="border border-dashed py-8">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <Plug />
        </EmptyMedia>
        <EmptyTitle>{t("empty.title")}</EmptyTitle>
        <EmptyDescription>{t("empty.description")}</EmptyDescription>
      </EmptyHeader>
    </Empty>
  );
}

export function McpSection() {
  const t = useTranslations("settingsMcp");
  const state = usePollingResource(mcpResource);
  const [adding, setAdding] = useState(false);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-4">
        <p className="text-muted-foreground text-sm">{t("description")}</p>
        {adding ? null : (
          <Button size="sm" variant="outline" className="shrink-0" onClick={() => setAdding(true)}>
            <Plus data-icon="inline-start" />
            {t("add")}
          </Button>
        )}
      </div>
      {adding ? <McpAddForm onDone={() => setAdding(false)} /> : null}
      <SectionState state={state} onRetry={() => void mcpResource.refresh()}>
        {({ servers }) => <ServerList servers={servers} adding={adding} />}
      </SectionState>
    </div>
  );
}
