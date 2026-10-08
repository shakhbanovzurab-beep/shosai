"use client";

import { useTranslations } from "use-intl";

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

import type { Hub } from "../../domain/contract";
import { deleteHub } from "../../model/hub-actions";
import { useHubWords } from "../../model/words";

/**
 * Deleting can't be undone, so it says plainly what goes (the hub and its addressing) and what stays
 * (meetings, tasks, documents). Archiving is the reversible way to put a hub away.
 */
export function DeleteDialog({
  hub,
  onOpenChange,
  onDeleted,
}: {
  hub: Hub | null;
  onOpenChange: (open: boolean) => void;
  onDeleted?: () => void;
}) {
  const t = useTranslations("hub");
  const common = useTranslations("common");
  const words = useHubWords();
  return (
    <AlertDialog open={hub !== null} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        {hub ? (
          <>
            <AlertDialogHeader>
              <AlertDialogTitle>{t("dialogs.deleteTitle", { name: hub.name })}</AlertDialogTitle>
              <AlertDialogDescription>{t("dialogs.deleteText")}</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{common("actions.cancel")}</AlertDialogCancel>
              <AlertDialogAction
                variant="destructive"
                onClick={async () => {
                  if (await deleteHub(words, hub)) onDeleted?.();
                }}
              >
                {t("dialogs.deleteConfirm")}
              </AlertDialogAction>
            </AlertDialogFooter>
          </>
        ) : null}
      </AlertDialogContent>
    </AlertDialog>
  );
}
