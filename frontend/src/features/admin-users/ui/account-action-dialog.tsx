"use client";

import { useState } from "react";

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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { ApiError } from "@/lib/api/errors";

import type { AccountAction, AdminUserCard } from "../domain/contract";
import { BLOCK_REASONS, UNBLOCK_REASONS } from "../domain/labels";
import { useAccountAction } from "../model/users";

const COPY: Record<AccountAction, { title: string; description: string; confirm: string }> = {
  block: {
    title: "Заблокировать аккаунт?",
    description:
      "Все сессии завершатся сразу, на всех устройствах. Человек не сможет войти, пока вы не разблокируете аккаунт. Данные не удаляются.",
    confirm: "Заблокировать",
  },
  unblock: {
    title: "Разблокировать аккаунт?",
    description: "Человек снова сможет войти. Завершённые при блокировке сессии не вернутся — нужно войти заново.",
    confirm: "Разблокировать",
  },
};

function problemOf(error: unknown): string {
  if (error instanceof ApiError && error.code === "account_state_conflict")
    return "Состояние аккаунта уже изменилось. Закройте окно и посмотрите карточку заново.";
  if (error instanceof ApiError && error.code === "admin_sign_in_required")
    return "Сессия администратора закончилась. Войдите снова.";
  return error instanceof Error ? error.message : "Не удалось выполнить действие.";
}

/** Смонтирован на одно открытие: причина каждый раз выбирается заново. */
function ActionForm({ card, action, onClose }: { card: AdminUserCard; action: AccountAction; onClose: () => void }) {
  const [reason, setReason] = useState("");
  const act = useAccountAction(card.user.id);
  const copy = COPY[action];
  const reasons = action === "block" ? BLOCK_REASONS : UNBLOCK_REASONS;

  function submit() {
    act.mutate({ action, reasonCode: reason }, { onSuccess: onClose });
  }

  return (
    <form action={submit} className="flex flex-col gap-4">
      <DialogHeader>
        <DialogTitle>{copy.title}</DialogTitle>
        <DialogDescription>
          {card.user.email}. {copy.description}
        </DialogDescription>
      </DialogHeader>
      <FieldGroup>
        <Field>
          <FieldLabel htmlFor="account-action-reason">Причина</FieldLabel>
          <Select value={reason} onValueChange={setReason}>
            <SelectTrigger id="account-action-reason">
              <SelectValue placeholder="Выберите причину" />
            </SelectTrigger>
            <SelectContent>
              {reasons.map((item) => (
                <SelectItem key={item.code} value={item.code}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <FieldDescription>Попадает в журнал аудита кодом, без личных данных.</FieldDescription>
        </Field>
        {act.isError ? <FieldError role="alert">{problemOf(act.error)}</FieldError> : null}
      </FieldGroup>
      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onClose}>
          Отмена
        </Button>
        <Button
          type="submit"
          variant={action === "block" ? "destructive" : "default"}
          disabled={act.isPending || reason === ""}
        >
          {act.isPending ? <Spinner data-icon="inline-start" /> : null}
          {copy.confirm}
        </Button>
      </DialogFooter>
    </form>
  );
}

export function AccountActionDialog({
  card,
  action,
  onClose,
}: {
  card: AdminUserCard;
  action: AccountAction | null;
  onClose: () => void;
}) {
  return (
    <Dialog open={action !== null} onOpenChange={(next) => (next ? undefined : onClose())}>
      <DialogContent className="sm:max-w-md">
        {action ? <ActionForm card={card} action={action} onClose={onClose} /> : null}
      </DialogContent>
    </Dialog>
  );
}
