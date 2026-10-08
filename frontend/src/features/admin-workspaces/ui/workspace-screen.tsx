"use client";

import { ArrowLeft, CirclePause, SearchX } from "lucide-react";

import { LoadError } from "@/components/feedback";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { Link } from "@/lib/navigation";

import { formatFullDateTime } from "../domain/format";
import { useWorkspace, workspaceResource } from "../model/resources";
import { EventsCard } from "./events-card";
import { MembersCard } from "./members-card";
import { WorkspaceHeader } from "./workspace-header";
import { WorkspaceSide } from "./workspace-side";

const back = (
  <Button variant="ghost" size="sm" className="-ml-2 w-fit" asChild>
    <Link href="/admin/workspaces">
      <ArrowLeft aria-hidden="true" />
      Все пространства
    </Link>
  </Button>
);

/** One workspace for the platform's team: who runs it, what it pays, how it's used, and what to do about it. */
export function WorkspaceScreen({ id }: { id: string }) {
  const state = useWorkspace(id);

  if (state.status === "loading")
    return (
      <div className="flex flex-col gap-4" aria-busy="true">
        {back}
        <span className="sr-only" role="status">
          Загрузка пространства…
        </span>
        <Skeleton className="h-36 rounded-xl" />
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <Skeleton className="h-96 rounded-xl" />
          <Skeleton className="h-96 rounded-xl" />
        </div>
      </div>
    );

  if (state.status === "error")
    return (
      <div className="flex flex-col gap-4">
        {back}
        <LoadError
          title="Не удалось открыть пространство"
          message={state.message}
          onRetry={() => void workspaceResource(id).refresh()}
          retryLabel="Повторить"
        />
      </div>
    );

  const workspace = state.data;
  if (!workspace)
    return (
      <div className="flex flex-col gap-4">
        {back}
        <Empty className="border border-dashed">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <SearchX />
            </EmptyMedia>
            <EmptyTitle>Пространство не найдено</EmptyTitle>
            <EmptyDescription>Возможно, его удалил владелец или другой администратор.</EmptyDescription>
          </EmptyHeader>
          <EmptyContent>
            <Button variant="outline" size="sm" asChild>
              <Link href="/admin/workspaces">К списку</Link>
            </Button>
          </EmptyContent>
        </Empty>
      </div>
    );

  return (
    <div className="flex flex-col gap-4">
      {back}
      <WorkspaceHeader workspace={workspace} />
      {workspace.suspension ? (
        <Alert>
          <CirclePause aria-hidden="true" />
          <AlertTitle>Доступ приостановлен {formatFullDateTime(workspace.suspension.at)}</AlertTitle>
          <AlertDescription>Причина: {workspace.suspension.reason}</AlertDescription>
        </Alert>
      ) : null}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="flex min-w-0 flex-col gap-4">
          <MembersCard workspace={workspace} />
          <EventsCard events={workspace.events} />
        </div>
        <WorkspaceSide workspace={workspace} />
      </div>
    </div>
  );
}
