"use client";

import { createContext, type ReactNode, use, useState } from "react";

import { lazyComponent } from "@/lib/lazy-component";

import type { ConnectCode, ConnectCodeCreate } from "../../domain/telegram-contract";

/*
 * Окно починки группы Telegram живёт над списком: когда группа подключилась, строка перестаёт быть
 * проблемной и её кнопка починки уходит, а окно должно остаться и показать «Подключено».
 */

export type ReconnectRequest = { title: string; intro: string; request: ConnectCodeCreate; code: ConnectCode };

const ReconnectContext = createContext<((next: ReconnectRequest) => void) | null>(null);

const ReconnectDialog = lazyComponent(() => import("./reconnect-dialog").then((m) => m.ReconnectDialog));

export function ReconnectHost({ workspaceId, children }: { workspaceId: string; children: ReactNode }) {
  const [open, setOpen] = useState<ReconnectRequest | null>(null);
  return (
    <ReconnectContext value={setOpen}>
      {children}
      {open ? (
        <ReconnectDialog
          workspaceId={workspaceId}
          title={open.title}
          intro={open.intro}
          request={open.request}
          code={open.code}
          onNewCode={(code) => setOpen({ ...open, code })}
          onClose={() => setOpen(null)}
        />
      ) : null}
    </ReconnectContext>
  );
}

/** Открыть окно починки с выданным кодом. */
export function useReconnect() {
  const open = use(ReconnectContext);
  if (!open) throw new Error("useReconnect needs ReconnectHost above it.");
  return open;
}
