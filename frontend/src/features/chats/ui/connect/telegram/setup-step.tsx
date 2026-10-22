"use client";

import { useActionState, useRef, useState } from "react";

import { Info } from "lucide-react";
import { useTranslations } from "use-intl";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DialogClose, DialogFooter } from "@/components/ui/dialog";
import { FieldGroup } from "@/components/ui/field";
import { Spinner } from "@/components/ui/spinner";

import type { ChatMode, ChatSettings } from "../../../domain/contract";
import type { ConnectCode, ConnectCodeCreate } from "../../../domain/telegram-contract";
import { requestCode } from "../../../model/chat-actions";
import { BindingField, DataNotice, ModeField } from "../connect-fields";

/*
 * Шаг «Настройка»: куда идут задачи, что читает Leo, согласие с хранением. Для «Каждого сообщения» — почему
 * Leo должен быть админом группы и что все его права можно выключить (CF-D1). Без согласия код не выдаётся:
 * ошибка у поля, фокус на нём.
 */

export function SetupStep({
  workspaceId,
  settings,
  bot,
  onCode,
}: {
  workspaceId: string;
  settings: ChatSettings;
  bot: string;
  onCode: (request: ConnectCodeCreate, code: ConnectCode) => void;
}) {
  const t = useTranslations("chatsConnect");
  const tc = useTranslations("common");
  const ta = useTranslations("chatsApi");
  const [projectId, setProjectId] = useState<string | null>(null);
  const [mode, setMode] = useState<ChatMode>("mentions");
  const [accepted, setAccepted] = useState(false);
  const [missing, setMissing] = useState(false);
  const notice = useRef<HTMLDivElement>(null);
  const [, submit, pending] = useActionState(async () => {
    if (!accepted) {
      setMissing(true);
      notice.current?.querySelector("button")?.focus();
      return null;
    }
    const request: ConnectCodeCreate = { project_id: projectId, mode, data_notice_accepted: true };
    const code = await requestCode(workspaceId, request, ta);
    if (code) onCode(request, code);
    return null;
  }, null);

  return (
    <form action={submit} className="flex min-h-0 flex-col gap-4">
      <div className="-mx-1 flex min-h-0 flex-col gap-4 overflow-y-auto px-1">
        <FieldGroup>
          <BindingField id="chat-binding" value={projectId} onChange={setProjectId} />
          <ModeField
            value={mode}
            onChange={setMode}
            hints={{ mentions: t("telegram.mentionsHint", { bot }), all: t("telegram.allHint") }}
          />
          {mode === "all" ? (
            <Alert>
              <Info />
              <AlertDescription>{t("telegram.adminExplained")}</AlertDescription>
            </Alert>
          ) : null}
          <div ref={notice}>
            <DataNotice
              mode={mode}
              settings={settings}
              checked={accepted}
              invalid={missing && !accepted}
              onChange={(next) => {
                setAccepted(next);
                if (next) setMissing(false);
              }}
            />
          </div>
        </FieldGroup>
        <p className="text-muted-foreground text-xs">{t("telegram.history")}</p>
      </div>
      <DialogFooter>
        <DialogClose asChild>
          <Button type="button" variant="outline">
            {tc("actions.cancel")}
          </Button>
        </DialogClose>
        <Button type="submit" disabled={pending}>
          {pending ? <Spinner data-icon="inline-start" /> : null}
          {pending ? t("telegram.gettingCode") : t("telegram.getCode")}
        </Button>
      </DialogFooter>
    </form>
  );
}
