"use client";

import { useState, useTransition } from "react";

import { Copy, Inbox, Trash2 } from "lucide-react";
import { useFormatter, useNow, useTranslations } from "next-intl";
import { toast } from "sonner";

import { ConfirmDestructive } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { usePollingResource } from "@/hooks/use-polling-resource";

import type { DataItem, DataKind } from "../../domain/data-contract";
import { removeAllData, removeDataItem } from "../../model/data-actions";
import { dataResources } from "../../model/settings-resources";

type ItemRowProps = { kind: DataKind; item: DataItem; now: Date; onRemove: () => void };

/** One item: its title and the backend's detail line as written, and how long ago it was created. */
function ItemRow({ kind, item, now, onRemove }: ItemRowProps) {
  const t = useTranslations("settingsPrivacy");
  const common = useTranslations("common");
  const format = useFormatter();
  const { url, title } = item;

  return (
    <li className="flex items-center gap-3 py-3">
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span dir="auto" className="truncate font-medium text-sm">
          {title}
        </span>
        <span className="truncate text-muted-foreground text-xs">
          <span dir="auto">{item.detail}</span> · {format.relativeTime(new Date(item.created_at), now)}
        </span>
      </div>
      {url ? (
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={t("copyLinkTo", { title })}
          onClick={() =>
            navigator.clipboard.writeText(url).then(
              () => toast.success(common("feedback.linkCopied")),
              () => toast.error(common("feedback.linkCopyFailed")),
            )
          }
        >
          <Copy />
        </Button>
      ) : null}
      <Button variant="ghost" size="icon-sm" aria-label={t(`kinds.${kind}.removeItem`, { title })} onClick={onRemove}>
        <Trash2 />
      </Button>
    </li>
  );
}

/** Lists one kind of the user's data (shared links, files, feedback) with per-item and bulk removal. */
export function DataListDialog({ kind, onClose }: { kind: DataKind; onClose: () => void }) {
  const t = useTranslations("settingsPrivacy");
  // The dialog only renders in the browser, so "3 days ago" counts from the browser's clock, kept current.
  const now = useNow({ updateInterval: 60_000 });
  const state = usePollingResource(dataResources[kind]);
  const [confirmAll, setConfirmAll] = useState(false);
  const [, startTransition] = useTransition();

  const items = state.status === "ready" ? state.data.items : [];
  const removeOne = (item: DataItem) => startTransition(() => removeDataItem(kind, item.id, t));
  const removeAll = () => startTransition(() => removeAllData(kind, t));

  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="flex max-h-[min(36rem,85dvh)] flex-col sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{t(`kinds.${kind}.title`)}</DialogTitle>
          <DialogDescription>{t(`kinds.${kind}.description`)}</DialogDescription>
        </DialogHeader>
        <div className="-mx-1 min-h-0 flex-1 overflow-y-auto px-1">
          {state.status === "loading" ? <Skeleton className="h-32 rounded-lg" /> : null}
          {state.status === "error" ? <p className="text-destructive text-sm">{state.message}</p> : null}
          {state.status === "ready" && items.length === 0 ? (
            <Empty className="py-8">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <Inbox />
                </EmptyMedia>
                <EmptyTitle>{t(`kinds.${kind}.empty`)}</EmptyTitle>
                <EmptyDescription>{t("nothingToManage")}</EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : null}
          <ul className="divide-y">
            {items.map((item) => (
              <ItemRow key={item.id} kind={kind} item={item} now={now} onRemove={() => removeOne(item)} />
            ))}
          </ul>
        </div>
        {items.length > 1 ? (
          <div className="flex justify-end border-t pt-4">
            <Button variant="outline" size="sm" className="text-destructive" onClick={() => setConfirmAll(true)}>
              {t(`kinds.${kind}.removeAll`)}
            </Button>
          </div>
        ) : null}
        <ConfirmDestructive
          open={confirmAll}
          title={t(`kinds.${kind}.confirmAll`)}
          description={t("cantUndo")}
          confirmLabel={t(`kinds.${kind}.removeAll`)}
          onConfirm={removeAll}
          onCancel={() => setConfirmAll(false)}
        />
      </DialogContent>
    </Dialog>
  );
}
