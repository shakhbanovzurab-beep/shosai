"use client";

import { CircleAlert } from "lucide-react";
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
import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";

type LoadErrorProps = {
  title: string;
  message: string;
  onRetry: () => void;
  /** The retry button's text; "Try again" in the interface language by default. */
  retryLabel?: string;
};

/** Shown when a tab's first load fails, with a way to try again. */
export function LoadError({ title, message, onRetry, retryLabel }: LoadErrorProps) {
  const t = useTranslations("common");
  return (
    <Empty className="border border-dashed">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <CircleAlert />
        </EmptyMedia>
        <EmptyTitle>{title}</EmptyTitle>
        <EmptyDescription>{message}</EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <Button variant="outline" size="sm" onClick={onRetry}>
          {retryLabel ?? t("actions.retry")}
        </Button>
      </EmptyContent>
    </Empty>
  );
}

type ConfirmDestructiveProps = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
  cancelLabel?: string;
};

/** Confirms an action the server can't undo, such as deleting vectors or credentials. */
export function ConfirmDestructive({
  open,
  title,
  description,
  confirmLabel,
  onConfirm,
  onCancel,
  cancelLabel,
}: ConfirmDestructiveProps) {
  const t = useTranslations("common");
  return (
    <AlertDialog open={open} onOpenChange={(next) => (next ? undefined : onCancel())}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{cancelLabel ?? t("actions.cancel")}</AlertDialogCancel>
          <AlertDialogAction variant="destructive" onClick={onConfirm}>
            {confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
