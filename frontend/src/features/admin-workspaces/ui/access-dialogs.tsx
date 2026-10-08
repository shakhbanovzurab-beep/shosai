"use client";

import { useActionState, useState } from "react";

import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldGroup } from "@/components/ui/field";
import { FieldDescription, FieldError, FieldLabel } from "@/components/ui/field-text";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";

import { type AdminWorkspaceDetail, SUSPEND_REASON_MAX } from "../domain/contract";
import { removeWorkspace, suspend } from "../model/actions";

type DialogProps = { workspace: AdminWorkspaceDetail; open: boolean; onClose: () => void };

/** Mounted per opening, so the reason starts empty. */
function SuspendForm({ workspace: w, onClose }: { workspace: AdminWorkspaceDetail; onClose: () => void }) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [, submit, pending] = useActionState(async () => {
    const failure = await suspend(w.id, reason.trim());
    if (failure) setError(failure);
    else onClose();
    return null;
  }, null);

  return (
    <form action={submit} noValidate className="flex flex-col gap-4">
      <DialogHeader>
        <DialogTitle>Приостановить «{w.name}»?</DialogTitle>
        <DialogDescription>
          Участники ({w.members}) перестанут открывать пространство и увидят, что доступ приостановлен. Ничего не
          удаляется: встречи, задачи и файлы вернутся, как только вы восстановите доступ. Оплата не останавливается.
        </DialogDescription>
      </DialogHeader>
      <FieldGroup>
        <Field>
          <FieldLabel htmlFor="suspend-reason">Причина</FieldLabel>
          <Textarea
            id="suspend-reason"
            rows={3}
            maxLength={SUSPEND_REASON_MAX}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Например: жалобы на спам-приглашения"
          />
          <FieldDescription>Видна только администраторам платформы, в журнале событий.</FieldDescription>
        </Field>
        {error ? <FieldError role="alert">{error}</FieldError> : null}
      </FieldGroup>
      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onClose}>
          Отмена
        </Button>
        <Button type="submit" variant="destructive" disabled={pending || reason.trim().length < 3}>
          {pending ? <Spinner data-icon="inline-start" /> : null}
          Приостановить
        </Button>
      </DialogFooter>
    </form>
  );
}

export function SuspendDialog({ workspace, open, onClose }: DialogProps) {
  return (
    <Dialog open={open} onOpenChange={(next) => (next ? undefined : onClose())}>
      <DialogContent className="sm:max-w-md">
        {open ? <SuspendForm workspace={workspace} onClose={onClose} /> : null}
      </DialogContent>
    </Dialog>
  );
}

/** Asks for the name to be typed: deleting can't be undone. */
function DeleteForm({ workspace: w, onClose }: { workspace: AdminWorkspaceDetail; onClose: () => void }) {
  const router = useRouter();
  const [typed, setTyped] = useState("");
  const matches = typed.trim() === w.name;
  const [, submit, pending] = useActionState(async () => {
    if (await removeWorkspace(w.id, w.name)) {
      onClose();
      router.push("/admin/workspaces");
    }
    return null;
  }, null);

  return (
    <form action={submit} noValidate className="flex flex-col gap-4">
      <DialogHeader>
        <DialogTitle>Удалить «{w.name}» навсегда?</DialogTitle>
        <DialogDescription>
          Удалятся проекты, задачи, решения и файлы, загруженные в пространство; участники ({w.members}) потеряют к нему
          доступ. Записи встреч и личные файлы останутся у их владельцев. Отменить это нельзя.
        </DialogDescription>
      </DialogHeader>
      <FieldGroup>
        <Field>
          <FieldLabel htmlFor="delete-confirm">Введите название, чтобы подтвердить</FieldLabel>
          <Input
            id="delete-confirm"
            autoComplete="off"
            spellCheck={false}
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            placeholder={w.name}
          />
        </Field>
        {!matches && typed ? <FieldError>Название не совпадает.</FieldError> : null}
      </FieldGroup>
      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onClose}>
          Отмена
        </Button>
        <Button type="submit" variant="destructive" disabled={pending || !matches}>
          {pending ? <Spinner data-icon="inline-start" /> : null}
          Удалить навсегда
        </Button>
      </DialogFooter>
    </form>
  );
}

export function DeleteDialog({ workspace, open, onClose }: DialogProps) {
  return (
    <Dialog open={open} onOpenChange={(next) => (next ? undefined : onClose())}>
      <DialogContent className="sm:max-w-md">
        {open ? <DeleteForm workspace={workspace} onClose={onClose} /> : null}
      </DialogContent>
    </Dialog>
  );
}
