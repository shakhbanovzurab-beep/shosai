"use client";

import { type ReactNode, useEffect } from "react";

import { CirclePause, ShieldQuestion } from "lucide-react";
import { useTranslations } from "use-intl";

import { LoadError } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { usePollingResource } from "@/hooks/use-polling-resource";
import { setClientCookie } from "@/lib/cookie.client";
import { Link } from "@/lib/navigation";

import { LAST_WORKSPACE_COOKIE, NEW_WORKSPACE_PATH } from "../../domain/paths";
import { resourcesOf, useWorkspaces, workspacesResource } from "../../model/resources";
import { WorkspaceContext } from "../../model/workspace-context";
import { InviteDialog } from "../members/invite-dialog";
import { EmptyMessage } from "./empty-message";
import { TeamPage } from "./layout";

function GateSkeleton() {
  const t = useTranslations("workspace");
  return (
    <TeamPage>
      <span className="sr-only">{t("gate.loading")}</span>
      <div className="flex flex-col gap-2">
        <Skeleton className="h-7 w-48" />
        <Skeleton className="h-4 w-80 max-w-full" />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Skeleton className="h-48 rounded-xl lg:col-span-2" />
        <Skeleton className="h-48 rounded-xl" />
      </div>
    </TeamPage>
  );
}

/** Loads the workspace's own state once the slug is known to be one of the account's workspaces. */
function WorkspaceState({ id, slug, children }: { id: string; slug: string; children: ReactNode }) {
  const t = useTranslations("workspace");
  const state = usePollingResource(resourcesOf(id).state);
  useEffect(() => {
    setClientCookie(LAST_WORKSPACE_COOKIE, encodeURIComponent(slug), 365);
  }, [slug]);
  if (state.status === "loading") return <GateSkeleton />;
  if (state.status === "error")
    return (
      <TeamPage>
        <LoadError
          title={t("gate.loadFailed")}
          message={state.message}
          onRetry={() => void resourcesOf(id).state.refresh()}
        />
      </TeamPage>
    );
  return (
    <WorkspaceContext value={{ id, slug }}>
      {children}
      <InviteDialog />
    </WorkspaceContext>
  );
}

/**
 * Every page of a workspace sits behind this: it finds the workspace by its slug among the account's
 * workspaces, explains a failed load, and says so plainly when the account isn't a member.
 */
export function WorkspaceGate({ slug, children }: { slug: string; children: ReactNode }) {
  const t = useTranslations("workspace");
  const workspaces = useWorkspaces();
  if (workspaces.status === "loading") return <GateSkeleton />;
  if (workspaces.status === "error")
    return (
      <TeamPage>
        <LoadError
          title={t("gate.listFailed")}
          message={workspaces.message}
          onRetry={() => void workspacesResource.refresh()}
        />
      </TeamPage>
    );
  const summary = workspaces.data.workspaces.find((w) => w.slug === slug);
  if (!summary)
    return (
      <TeamPage>
        <EmptyMessage
          icon={ShieldQuestion}
          title={t("gate.unavailable")}
          text={t("gate.unavailableHint")}
          action={
            <>
              <Button asChild variant="outline">
                <Link href="/app/productivity">{t("gate.backToPersonal")}</Link>
              </Button>
              <Button asChild variant="ghost">
                <Link href={NEW_WORKSPACE_PATH}>{t("createWorkspace")}</Link>
              </Button>
            </>
          }
        />
      </TeamPage>
    );
  if (summary.suspended)
    return (
      <TeamPage>
        <EmptyMessage
          icon={CirclePause}
          title={t("gate.suspended", { name: summary.name })}
          text={t(summary.role === "owner" ? "gate.suspendedOwnerHint" : "gate.suspendedHint")}
          action={
            <Button asChild variant="outline">
              <Link href="/app/productivity">{t("gate.backToPersonal")}</Link>
            </Button>
          }
        />
      </TeamPage>
    );
  return (
    <WorkspaceState key={summary.id} id={summary.id} slug={summary.slug}>
      {children}
    </WorkspaceState>
  );
}
