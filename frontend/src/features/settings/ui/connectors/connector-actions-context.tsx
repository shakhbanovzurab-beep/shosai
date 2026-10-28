"use client";

import { createContext, type ReactNode, use, useState } from "react";

import type { Connector } from "../../domain/connectors-contract";
import { useConnectorOAuth } from "../../model/use-connector-oauth";
import { CredentialsDialog } from "./credentials-dialog";
import { DisconnectDialog } from "./disconnect-dialog";

/*
 * Действия строк Settings › Connectors: поток OAuth, вопрос перед отключением и форма секрета. Диалоги живут один
 * раз на раздел, строки только просят их открыть — без пробрасывания колбэков через таблицу.
 */

type Asked = { kind: "disconnect" | "credentials"; connector: Connector };

interface ConnectorActions {
  readonly pendingId: string | null;
  /** Подключить или переподключить: OAuth в окне провайдера, секрет — в форме. */
  readonly connect: (connector: Connector) => void;
  readonly askDisconnect: (connector: Connector) => void;
}

const ConnectorActionsContext = createContext<ConnectorActions | null>(null);

export function useConnectorActions(): ConnectorActions {
  const value = use(ConnectorActionsContext);
  if (!value) throw new Error("useConnectorActions must be used inside <ConnectorActionsProvider>");
  return value;
}

export function ConnectorActionsProvider({ children }: { children: ReactNode }) {
  const oauth = useConnectorOAuth();
  const [asked, setAsked] = useState<Asked | null>(null);
  const close = () => setAsked(null);
  const actions: ConnectorActions = {
    pendingId: oauth.pendingId,
    connect: (connector) => {
      if (connector.auth === "oauth") void oauth.connect(connector);
      else setAsked({ kind: "credentials", connector });
    },
    askDisconnect: (connector) => setAsked({ kind: "disconnect", connector }),
  };

  return (
    <ConnectorActionsContext value={actions}>
      {children}
      <DisconnectDialog connector={asked?.kind === "disconnect" ? asked.connector : null} onClose={close} />
      <CredentialsDialog connector={asked?.kind === "credentials" ? asked.connector : null} onClose={close} />
    </ConnectorActionsContext>
  );
}
