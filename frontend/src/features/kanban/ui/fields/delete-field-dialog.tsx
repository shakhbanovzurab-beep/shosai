"use client";

import { useFormatter, useTranslations } from "use-intl";

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

import type { CustomSticker, OwnedSticker } from "../../domain/stickers-contract";

/**
 * Удалить поле совсем: подтверждение называет доски, с которых оно уйдёт, и сколько задач потеряют значение —
 * значения видят все, кто видит задачи (KG-D4).
 */
export function DeleteFieldDialog({
  sticker,
  owned,
  open,
  onOpenChange,
  onConfirm,
}: {
  sticker: CustomSticker;
  owned: OwnedSticker | undefined;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
}) {
  const t = useTranslations("kanbanFields");
  const tc = useTranslations("common");
  const format = useFormatter();
  const boards = format.list(owned?.boards.map((board) => board.name) ?? [], { type: "conjunction" });
  const tasks = owned?.usage.tasks ?? 0;
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t("delete.title", { name: sticker.name })}</AlertDialogTitle>
          <AlertDialogDescription>
            {tasks > 0 ? t("delete.body", { boards, tasks }) : t("delete.bodyNoValues", { boards })}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{tc("actions.cancel")}</AlertDialogCancel>
          <AlertDialogAction variant="destructive" onClick={onConfirm}>
            {t("delete.confirm")}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
