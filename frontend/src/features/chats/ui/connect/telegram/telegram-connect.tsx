"use client";

import { useState } from "react";

import type { ChatSettings } from "../../../domain/contract";
import type { ConnectCode, ConnectCodeCreate } from "../../../domain/telegram-contract";
import { StepFocus } from "../step-focus";
import { AddBotStep } from "./add-bot-step";
import { SetupStep } from "./setup-step";

/*
 * Подключение группы Telegram (§3.2 плана): настройка → код и ожидание группы → подключено. Запрос кода
 * хранится, чтобы «Получить новый код» после истечения или отказа повторил его без нового заполнения.
 */

export function TelegramConnect({
  workspaceId,
  settings,
  bot,
  onDone,
}: {
  workspaceId: string;
  settings: ChatSettings;
  bot: string;
  onDone: () => void;
}) {
  const [issued, setIssued] = useState<{ request: ConnectCodeCreate; code: ConnectCode } | null>(null);

  if (issued === null)
    return (
      <StepFocus key="setup">
        <SetupStep
          workspaceId={workspaceId}
          settings={settings}
          bot={bot}
          onCode={(request, code) => setIssued({ request, code })}
        />
      </StepFocus>
    );
  return (
    <StepFocus key={issued.code.id}>
      <AddBotStep
        workspaceId={workspaceId}
        request={issued.request}
        code={issued.code}
        onNewCode={(code) => setIssued({ request: issued.request, code })}
        onBack={() => setIssued(null)}
        onDone={onDone}
      />
    </StepFocus>
  );
}
