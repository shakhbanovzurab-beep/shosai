"use client";

import { useState } from "react";

import { useRouter } from "next/navigation";

import { LayoutGrid, Plus } from "lucide-react";
import { useTranslations } from "next-intl";

import { LoadError } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

import { isHubErrorCode } from "../../domain/errors";
import { type HubsFilter, hubPath, hubsPath } from "../../domain/paths";
import { retry, useHubList } from "../../model/hooks";
import { useErrorText } from "../../model/words";
import { ComingUp } from "../brief/meeting-prep";
import { TodayBrief } from "../brief/today-brief";
import { HubDialogs, useHubDialogs } from "../dialogs/hub-dialogs";
import { NameDialog } from "../dialogs/name-dialog";
import { HubRow } from "./hub-row";

function ListSkeleton() {
  return (
    <div className="flex flex-col divide-y rounded-xl border" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <div key={i} className="flex flex-col gap-2 px-4 py-3.5">
          <Skeleton className="h-5 w-1/3" />
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-3 w-2/5" />
        </div>
      ))}
    </div>
  );
}

function Hubs({ filter, onCreate }: { filter: HubsFilter; onCreate: () => void }) {
  const t = useTranslations("hub");
  const common = useTranslations("common");
  const errorText = useErrorText();
  const list = useHubList(filter === "all");
  const dialogs = useHubDialogs();
  if (list.status === "loading") return <ListSkeleton />;
  if (list.status === "error")
    return (
      <LoadError
        title={t("list.loadError")}
        message={errorText(isHubErrorCode(list.message) ? list.message : "unknown")}
        onRetry={() => void retry.hubs()}
        retryLabel={common("actions.retry")}
      />
    );
  const hubs = list.data.hubs;
  if (hubs.length === 0)
    return (
      <Empty className="min-h-72 border border-dashed">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <LayoutGrid />
          </EmptyMedia>
          <EmptyTitle>{t("list.emptyTitle")}</EmptyTitle>
          <EmptyDescription>{t("list.emptyText")}</EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <Button onClick={onCreate}>
            <Plus data-icon="inline-start" />
            {t("list.newHub")}
          </Button>
          {filter === "active" ? <p className="text-muted-foreground text-xs">{t("list.noActive")}</p> : null}
        </EmptyContent>
      </Empty>
    );
  return (
    <>
      <ul className="flex flex-col divide-y rounded-xl border">
        {hubs.map((hub) => (
          <HubRow key={hub.id} hub={hub} onAction={dialogs.open} />
        ))}
      </ul>
      <HubDialogs request={dialogs.request} onClose={dialogs.close} />
    </>
  );
}

/**
 * The Hub section: every hub with what's most urgent in it, today's brief and the meetings coming
 * up. Nothing here pulls people back: no unread counts, no streaks, no red dots.
 */
export function HubsScreen({ filter }: { filter: HubsFilter }) {
  const t = useTranslations("hub");
  const router = useRouter();
  const [creating, setCreating] = useState(false);
  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 pb-24">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex max-w-2xl flex-col gap-1.5">
          <h1 className="font-semibold text-2xl tracking-tight">{t("list.title")}</h1>
          <p className="text-pretty text-muted-foreground text-sm">{t("list.lead")}</p>
        </div>
        <Button onClick={() => setCreating(true)}>
          <Plus data-icon="inline-start" />
          {t("list.newHub")}
        </Button>
      </header>
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_22rem] lg:gap-10">
        <div className="lg:col-start-2 lg:row-start-1">
          <TodayBrief />
        </div>
        <section
          aria-labelledby="hubs-list"
          className="flex min-w-0 flex-col gap-3 lg:col-start-1 lg:row-span-2 lg:row-start-1"
        >
          <div className="flex items-center justify-between gap-3">
            <h2 id="hubs-list" className="sr-only">
              {t("list.title")}
            </h2>
            <ToggleGroup
              type="single"
              variant="outline"
              size="sm"
              value={filter}
              aria-label={t("list.filterLabel")}
              onValueChange={(value) => {
                if (value === "active" || value === "all") router.replace(hubsPath(value), { scroll: false });
              }}
            >
              <ToggleGroupItem value="active">{t("list.filterActive")}</ToggleGroupItem>
              <ToggleGroupItem value="all">{t("list.filterAll")}</ToggleGroupItem>
            </ToggleGroup>
          </div>
          <Hubs filter={filter} onCreate={() => setCreating(true)} />
        </section>
        <div className="lg:col-start-2 lg:row-start-2">
          <ComingUp />
        </div>
      </div>
      <NameDialog
        hub={null}
        open={creating}
        onOpenChange={setCreating}
        onCreated={(hub) => router.push(hubPath(hub.id))}
      />
    </div>
  );
}
