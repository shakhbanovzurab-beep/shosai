"use client";

import { SearchX } from "lucide-react";
import { useTranslations } from "use-intl";

import { LoadError } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { Link, useRouter, useSearchParams } from "@/lib/navigation";

import { isHubErrorCode } from "../../domain/errors";
import { HUBS_PATH, hubPath, OPEN_PARAM, threadPath } from "../../domain/paths";
import { retry, useHubList } from "../../model/hooks";
import { useErrorText } from "../../model/words";
import { HubDialogs, useHubDialogs } from "../dialogs/hub-dialogs";
import { ThreadSheet } from "../thread/thread-sheet";
import { UnresolvedBlock, UnresolvedSkeleton } from "../unresolved/unresolved-block";
import { Charter } from "./charter";
import { DigestBlock } from "./digest-block";
import { FeedBlock } from "./feed-block";
import { HubHeader } from "./hub-header";
import { MaterialsBlock } from "./materials-block";

function PageSkeleton() {
  const common = useTranslations("common");
  return (
    <div className="flex flex-col gap-10" aria-busy="true">
      <span className="sr-only">{common("feedback.loading")}</span>
      <div className="flex flex-col gap-3">
        <Skeleton className="h-7 w-24" />
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-4 w-2/5" />
      </div>
      <div className="flex flex-col gap-3">
        <Skeleton className="h-5 w-40" />
        <UnresolvedSkeleton />
      </div>
    </div>
  );
}

function NotFound() {
  const t = useTranslations("hub");
  return (
    <Empty className="min-h-80 border border-dashed">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <SearchX />
        </EmptyMedia>
        <EmptyTitle>{t("page.notFoundTitle")}</EmptyTitle>
        <EmptyDescription>{t("page.notFoundText")}</EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <Button asChild variant="outline">
          <Link href={HUBS_PATH}>{t("page.back")}</Link>
        </Button>
      </EmptyContent>
    </Empty>
  );
}

/**
 * The hub page. The order of its blocks is the order of meaning: the hub and its purpose, what's
 * unresolved, what changed at the last meeting, what happened here, and the materials.
 */
function HubPage({ hubId }: { hubId: string }) {
  const t = useTranslations("hub");
  const common = useTranslations("common");
  const errorText = useErrorText();
  const router = useRouter();
  const list = useHubList(true);
  const dialogs = useHubDialogs();
  const openId = useSearchParams().get(OPEN_PARAM);
  // The panel's address changes without a server round trip; Back closes it again.
  const open = (threadId: string) => window.history.pushState(null, "", threadPath(hubId, threadId));
  const close = () => window.history.pushState(null, "", hubPath(hubId));

  if (list.status === "loading") return <PageSkeleton />;
  if (list.status === "error")
    return (
      <LoadError
        title={t("page.loadError")}
        message={errorText(isHubErrorCode(list.message) ? list.message : "unknown")}
        onRetry={() => void retry.hubs()}
        retryLabel={common("actions.retry")}
      />
    );
  const hub = list.data.hubs.find((h) => h.id === hubId);
  if (!hub) return <NotFound />;

  return (
    <>
      <div className="flex flex-col gap-5">
        <HubHeader hub={hub} onAction={dialogs.open} />
        <Charter hub={hub} />
      </div>
      <UnresolvedBlock hubId={hub.id} onOpen={open} />
      <DigestBlock hubId={hub.id} onOpen={open} />
      <FeedBlock hubId={hub.id} />
      <MaterialsBlock hubId={hub.id} />
      <ThreadSheet threadId={openId} onClose={close} onOpen={open} />
      <HubDialogs request={dialogs.request} onClose={dialogs.close} onDeleted={() => router.push(HUBS_PATH)} />
    </>
  );
}

export function HubScreen({ hubId }: { hubId: string }) {
  return (
    // Bottom padding keeps the last block clear of the floating Leo button.
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-10 pb-24">
      <HubPage hubId={hubId} />
    </div>
  );
}
