"use client";

import { ExternalLink } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { DialogFooter } from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { useNow } from "@/hooks/use-now";

import { minutesLeft } from "../../../domain/chat-rules";
import { type ConnectCode, type ConnectCodeCreate, displayCode } from "../../../domain/telegram-contract";
import { useCodeStatus } from "../../../model/resources";
import { CopyValue } from "../copy-value";
import { CodeEnded } from "./code-ended";
import { ConnectedStep } from "./connected-step";

/*
 * Шаг «Добавьте Leo в группу»: код, ссылка, которая открывает Telegram и выбор группы, ручной путь командой и
 * ожидание группы. Код, который ждал, когда окно закрыли, отменяет модель (`resources.ts`).
 */

export function AddBotStep({
  workspaceId,
  request,
  code,
  onNewCode,
  onBack,
  backLabel,
  onDone,
}: {
  workspaceId: string;
  request: ConnectCodeCreate;
  code: ConnectCode;
  onNewCode: (code: ConnectCode) => void;
  onBack: () => void;
  /** Подпись кнопки ухода: «Назад» в окне подключения, «Закрыть» в окне починки. */
  backLabel?: string;
  onDone: () => void;
}) {
  const t = useTranslations("chatsConnect");
  const state = useCodeStatus(workspaceId, code.id);
  const status = state.status === "ready" ? state.data : null;
  const now = useNow();

  if (status?.status === "connected" && status.connection)
    return <ConnectedStep connection={status.connection} code={code} onDone={onDone} />;
  if (status?.status === "expired" || status?.status === "refused")
    return (
      <CodeEnded workspaceId={workspaceId} request={request} status={status} onNewCode={onNewCode} onBack={onBack} />
    );

  const url = code.mode === "all" ? code.add_as_admin_url : code.add_url;
  return (
    <div className="flex min-h-0 flex-col gap-4">
      <div className="-mx-1 flex min-h-0 flex-col gap-4 overflow-y-auto px-1">
        <div className="flex flex-col gap-1.5">
          <span className="font-medium text-sm">{t("add.code")}</span>
          <CopyValue
            value={code.code}
            shown={displayCode(code.code)}
            copyLabel={t("add.copyCode")}
            copied={t("add.codeCopied")}
            size="code"
          />
        </div>
        <Button asChild>
          <a href={url} target="_blank" rel="noopener noreferrer">
            {code.mode === "all" ? t("add.openAdmin") : t("add.open")}
            <ExternalLink data-icon="inline-end" className="rtl:-scale-x-100" />
          </a>
        </Button>
        <div className="flex flex-col gap-1.5">
          <p className="text-muted-foreground text-sm">{t("add.manual", { bot: code.bot_username })}</p>
          <CopyValue
            value={code.command}
            shown={code.command}
            copyLabel={t("add.copyCommand")}
            copied={t("add.commandCopied")}
            size="command"
          />
        </div>
        <p role="status" className="flex items-center gap-2 text-sm">
          <Spinner />
          {t("add.waiting")}
        </p>
        {now === null ? null : (
          <p className="text-muted-foreground text-xs tabular-nums">
            {t("add.expiresIn", { minutes: minutesLeft(code.expires_at, now) })}
          </p>
        )}
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onBack}>
          {backLabel ?? t("back")}
        </Button>
      </DialogFooter>
    </div>
  );
}
