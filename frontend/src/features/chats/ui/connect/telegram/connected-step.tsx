"use client";

import { CircleCheck, ExternalLink, ShieldAlert } from "lucide-react";
import { useTranslations } from "use-intl";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DialogFooter } from "@/components/ui/dialog";

import type { ChatConnection } from "../../../domain/contract";
import type { ConnectCode } from "../../../domain/telegram-contract";
import { useBindingText } from "../../binding-text";

/*
 * Подключено: какая группа, куда идут задачи и что читает Leo. Если для «Каждого сообщения» Telegram ещё
 * не сообщил, что Leo — админ группы, здесь же ссылка, которая открывает добавление админом (CF-D1).
 */

export function ConnectedStep({
  connection,
  code,
  onDone,
}: {
  connection: ChatConnection;
  code: ConnectCode;
  onDone: () => void;
}) {
  const t = useTranslations("chatsConnect");
  const tc = useTranslations("chats");
  const bindingText = useBindingText();

  return (
    <div className="flex flex-col gap-4">
      <div role="status" className="flex items-start gap-3">
        <CircleCheck aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-primary" />
        <div className="flex min-w-0 flex-col gap-1">
          <p dir="auto" className="font-medium">
            {t("connected.title", { chat: connection.title })}
          </p>
          <p className="text-muted-foreground text-sm">
            {t("connected.summary", { binding: bindingText(connection.binding), mode: tc(`mode.${connection.mode}`) })}
          </p>
        </div>
      </div>
      {connection.problem === "rights_missing" ? (
        <Alert>
          <ShieldAlert />
          <AlertDescription className="flex flex-col items-start gap-3">
            {t("connected.makeAdmin")}
            <Button asChild size="sm" variant="outline">
              <a href={code.add_as_admin_url} target="_blank" rel="noopener noreferrer">
                {t("connected.openAdmin")}
                <ExternalLink data-icon="inline-end" className="rtl:-scale-x-100" />
              </a>
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}
      <DialogFooter>
        <Button type="button" onClick={onDone}>
          {t("connected.done")}
        </Button>
      </DialogFooter>
    </div>
  );
}
