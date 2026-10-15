"use client";

import { useState } from "react";

import { LockKeyhole, LockKeyholeOpen } from "lucide-react";

import { Button } from "@/components/ui/button";

import type { AccountAction, AdminUserCard } from "../domain/contract";
import { AccountActionDialog } from "./account-action-dialog";

/** Что нельзя сделать с аккаунтом и почему: блокируется только активный, разблокируется только заблокированный. */
const UNAVAILABLE: Partial<Record<AdminUserCard["user"]["state"], string>> = {
  banned: "Аккаунт закрыт навсегда до отказа от бана; разблокировать его нельзя.",
  deletion_scheduled: "Человек попросил удалить аккаунт: пока идёт окно удаления, блокировать нечего.",
  deleting: "Аккаунт удаляется.",
  transferring: "Аккаунт переносится в другой дом данных; действия доступны после переноса.",
  deleted: "Аккаунт удалён.",
};

export function AccountActions({ card }: { card: AdminUserCard }) {
  const [opening, setOpening] = useState<AccountAction | null>(null);
  const { state } = card.user;
  const reason = UNAVAILABLE[state];

  return (
    <div className="flex flex-wrap items-center gap-2">
      {state === "active" ? (
        <Button variant="outline" size="sm" onClick={() => setOpening("block")}>
          <LockKeyhole aria-hidden="true" />
          Заблокировать
        </Button>
      ) : null}
      {state === "frozen" ? (
        <Button variant="outline" size="sm" onClick={() => setOpening("unblock")}>
          <LockKeyholeOpen aria-hidden="true" />
          Разблокировать
        </Button>
      ) : null}
      {reason ? <p className="text-muted-foreground text-sm">{reason}</p> : null}
      <AccountActionDialog card={card} action={opening} onClose={() => setOpening(null)} />
    </div>
  );
}
