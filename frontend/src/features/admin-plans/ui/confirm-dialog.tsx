"use client";

import { type ReactNode, useState } from "react";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

type ConfirmDialogProps = {
  open: boolean;
  title: string;
  children: ReactNode;
  confirmLabel: string;
  destructive?: boolean;
  /** Resolves when done; the dialog stays open (and busy) until then, and closes only on success. */
  onConfirm: () => Promise<boolean>;
  onClose: () => void;
};

/** Asks before an action that changes or removes data; stays open while the request runs. */
export function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel,
  destructive,
  onConfirm,
  onClose,
}: ConfirmDialogProps) {
  const [pending, setPending] = useState(false);

  function confirm() {
    setPending(true);
    void onConfirm()
      .then((done) => {
        if (done) onClose();
      })
      .finally(() => setPending(false));
  }

  return (
    <AlertDialog open={open} onOpenChange={(next) => (next || pending ? undefined : onClose())}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="flex flex-col gap-2">{children}</div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending}>Отмена</AlertDialogCancel>
          <Button variant={destructive ? "destructive" : "default"} disabled={pending} onClick={confirm}>
            {pending ? <Spinner data-icon="inline-start" aria-label="Выполняется" /> : null}
            {confirmLabel}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
