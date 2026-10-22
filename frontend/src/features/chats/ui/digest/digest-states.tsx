"use client";

import type { ReactNode } from "react";

import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

/** Рамка карточки дайджеста в ответе Leo; `label` — подпись артефакта от сервера. */
export function DigestFrame({ label, busy, children }: { label: string; busy?: boolean; children: ReactNode }) {
  return (
    <article
      aria-label={label}
      aria-busy={busy}
      className="@container flex flex-col gap-4 rounded-2xl border bg-card px-4 py-3.5 text-card-foreground"
    >
      {children}
    </article>
  );
}

/** Пока грузится: шапка и три строки в форме карточки — без сдвига, когда она придёт. */
export function DigestSkeleton({ label }: { label: string }) {
  const t = useTranslations("chatsDigest");
  return (
    <DigestFrame label={label} busy>
      <span className="sr-only">{t("states.loading")}</span>
      <div className="flex items-center gap-3" aria-hidden="true">
        <Skeleton className="size-8 rounded-lg" />
        <div className="flex flex-1 flex-col gap-1.5">
          <Skeleton className="h-3.5 w-40" />
          <Skeleton className="h-3 w-56" />
        </div>
      </div>
      <div className="flex flex-col gap-2.5" aria-hidden="true">
        <Skeleton className="h-3.5 w-11/12" />
        <Skeleton className="h-3.5 w-4/5" />
        <Skeleton className="h-3.5 w-2/3" />
      </div>
    </DigestFrame>
  );
}

/** Дайджеста больше нет: чат отключили или его сообщения истекли. */
export function DigestGone({ label }: { label: string }) {
  const t = useTranslations("chatsDigest");
  return (
    <DigestFrame label={label}>
      <p className="text-muted-foreground text-sm">{t("states.gone")}</p>
    </DigestFrame>
  );
}

export function DigestFailed({ label, onRetry }: { label: string; onRetry: () => void }) {
  const t = useTranslations("chatsDigest");
  const common = useTranslations("common");
  return (
    <DigestFrame label={label}>
      <div role="alert" className="flex flex-wrap items-center gap-3 text-sm">
        {t("states.failed")}
        <Button variant="outline" size="sm" onClick={onRetry}>
          {common("actions.retry")}
        </Button>
      </div>
    </DigestFrame>
  );
}
