"use client";

import { createContext, type ReactNode, use, useRef, useState } from "react";

import { focusBack } from "@/lib/focus-back";
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
  // Кнопка починки, с которой открыли окно: фокус вернётся к ней, если строка ещё не починена.
  const opener = useRef<HTMLElement | null>(null);
  const show = (next: ReconnectRequest) => {
    if (open === null) opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setOpen(next);
  };
  return (
    <ReconnectContext value={show}>
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
          onCloseAutoFocus={(event) => focusBack(event, opener)}
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
