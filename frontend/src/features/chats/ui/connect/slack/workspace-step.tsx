"use client";

import { ChevronRight, Plus } from "lucide-react";
import { useTranslations } from "use-intl";

import { MessengerTile } from "@/components/brand/messenger-mark";
import { LoadError } from "@/components/feedback";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";

import type { SlackInstallation } from "../../../domain/slack-contract";
import { chatResources, useInstallations } from "../../../model/resources";
import { useSlackHandoff } from "../../../model/slack-handoff";

/*
 * Пространство Slack: выбрать подключённое, переподключить то, у которого кончился доступ, или установить
 * приложение в новое. Пока человек в окне Slack, здесь — ожидание.
 */

function InstallationButton({ item, onPick }: { item: SlackInstallation; onPick: (id: string) => void }) {
  const t = useTranslations("chatsConnect");
  return (
    <button
      type="button"
      onClick={() => onPick(item.id)}
      className="flex items-center gap-3 rounded-lg border p-3 text-start transition-colors hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring"
    >
      <MessengerTile messenger="slack" />
      <span className="flex min-w-0 flex-1 flex-col">
        <span title={item.team.name} className="truncate font-medium">
          <bdi>{item.team.name}</bdi>
        </span>
        <span className="text-muted-foreground text-xs">
          {t("slack.channelsConnected", { count: item.connections })}
        </span>
      </span>
      <ChevronRight aria-hidden="true" className="size-4 text-muted-foreground rtl:-scale-x-100" />
    </button>
  );
}

export function WorkspaceStep({ workspaceId, onPick }: { workspaceId: string; onPick: (id: string) => void }) {
  const t = useTranslations("chatsConnect");
  const ta = useTranslations("chatsApi");
  const tc = useTranslations("common");
  const state = useInstallations(workspaceId);
  const handoff = useSlackHandoff(workspaceId, { t, ta }, onPick);

  if (state.status === "loading") return <Skeleton className="h-16 w-full rounded-lg" />;
  if (state.status === "error")
    return (
      <LoadError
        title={t("slack.loadError")}
        message={t("slack.loadErrorHint")}
        retryLabel={tc("actions.retry")}
        onRetry={() => void chatResources(workspaceId).installations.refresh()}
      />
    );
  if (handoff.waiting)
    return (
      <p role="status" className="flex items-center gap-2 py-6 text-sm">
        <Spinner aria-hidden="true" />
        {t("slack.finishInSlack")}
      </p>
    );
  const items = state.data.items;
  return (
    <div className="flex flex-col gap-2">
      {items.map((item) =>
        item.state === "working" ? (
          <InstallationButton key={item.id} item={item} onPick={onPick} />
        ) : (
          <div key={item.id} className="flex items-center gap-3 rounded-lg border p-3">
            <MessengerTile messenger="slack" />
            <span title={item.team.name} className="min-w-0 flex-1 truncate font-medium">
              <bdi>{item.team.name}</bdi>
            </span>
            <Badge variant="destructive">{t("slack.accessEnded")}</Badge>
            <Button size="sm" variant="outline" onClick={() => void handoff.start(item.id)}>
              {t("slack.reconnect")}
            </Button>
          </div>
        ),
      )}
      <Button variant={items.length > 0 ? "outline" : "default"} onClick={() => void handoff.start()}>
        <Plus data-icon="inline-start" />
        {items.length > 0 ? t("slack.addAnother") : t("slack.connectSlack")}
      </Button>
    </div>
  );
}
