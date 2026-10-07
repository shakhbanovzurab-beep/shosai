"use client";

import { useTranslations } from "next-intl";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Skeleton } from "@/components/ui/skeleton";

import type { Hub } from "../../domain/contract";
import { byUrgency } from "../../domain/urgency";
import { useHubThreads } from "../../model/hooks";
import { archiveHub } from "../../model/hub-actions";
import { useHubWords } from "../../model/words";
import { useHubPhrases } from "../shared/phrases";
import { GapIcon } from "../shared/urgency";

/** What's still open, read with the hub's one request for its rows. */
function OpenLeft({ hub }: { hub: Hub }) {
  const t = useTranslations("hub");
  const say = useHubPhrases();
  const state = useHubThreads(hub.id);
  if (state.status === "loading")
    return (
      <div className="flex flex-col gap-2" aria-busy="true">
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-4 w-3/4" />
      </div>
    );
  // Without the list, the count the hub row already knows still says what's at stake.
  const open = state.status === "ready" ? byUrgency(state.data.data) : [];
  const count = state.status === "ready" ? open.length : hub.openThreads;
  if (count === 0) return <AlertDialogDescription>{t("dialogs.nothingLeft")}</AlertDialogDescription>;
  return (
    <div className="flex flex-col gap-2">
      <AlertDialogDescription>{t("dialogs.openLeft", { count })}</AlertDialogDescription>
      {open.length > 0 ? (
        <ul className="flex max-h-56 flex-col gap-2 overflow-y-auto text-sm">
          {open.map((thread) => (
            <li key={thread.id} className="flex flex-col">
              <span dir="auto" className="font-medium">
                {thread.subject}
              </span>
              <span className="flex items-center gap-1.5 text-muted-foreground text-xs">
                {thread.gap ? <GapIcon kind={thread.gap.kind} className="size-3" /> : null}
                {say.status(thread)}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/**
 * The one place the Hub stops a person: before archiving, it shows what is still open. With nothing
 * open it is a single confirmation. Restoring needs no question.
 */
export function ArchiveDialog({ hub, onOpenChange }: { hub: Hub | null; onOpenChange: (open: boolean) => void }) {
  const t = useTranslations("hub");
  const common = useTranslations("common");
  const words = useHubWords();
  return (
    <AlertDialog open={hub !== null} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        {hub ? (
          <>
            <AlertDialogHeader>
              <AlertDialogTitle>{t("dialogs.archiveTitle", { name: hub.name })}</AlertDialogTitle>
            </AlertDialogHeader>
            <OpenLeft hub={hub} />
            <AlertDialogFooter>
              <AlertDialogCancel>{common("actions.cancel")}</AlertDialogCancel>
              <AlertDialogAction onClick={() => void archiveHub(words, hub)}>
                {t("dialogs.archiveConfirm")}
              </AlertDialogAction>
            </AlertDialogFooter>
          </>
        ) : null}
      </AlertDialogContent>
    </AlertDialog>
  );
}
