"use client";

import { useActionState } from "react";

import { CircleAlert } from "lucide-react";
import { useTranslations } from "use-intl";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DialogFooter } from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";

import type { ConnectCode, ConnectCodeCreate, ConnectStatus } from "../../../domain/telegram-contract";
import { requestCode } from "../../../model/chat-actions";

/*
 * Код кончился: истёк или группа отказала (уже подключена к другому пространству, не группа, другая группа,
 * мест нет). Новый код — тем же запросом, без нового заполнения.
 */

export function CodeEnded({
  workspaceId,
  request,
  status,
  onNewCode,
  onBack,
}: {
  workspaceId: string;
  request: ConnectCodeCreate;
  status: ConnectStatus;
  onNewCode: (code: ConnectCode) => void;
  onBack: () => void;
}) {
  const t = useTranslations("chatsConnect");
  const ta = useTranslations("chatsApi");
  const [, renew, pending] = useActionState(async () => {
    const code = await requestCode(workspaceId, request, ta);
    if (code) onNewCode(code);
    return null;
  }, null);
  const words = status.status === "refused" && status.refusal ? t(`refusal.${status.refusal}`) : t("add.expiredHint");

  return (
    <form action={renew} className="flex flex-col gap-4">
      <Alert variant="destructive">
        <CircleAlert />
        <AlertTitle>{status.status === "refused" ? t("refusal.title") : t("add.expired")}</AlertTitle>
        <AlertDescription>{words}</AlertDescription>
      </Alert>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onBack}>
          {t("back")}
        </Button>
        <Button type="submit" disabled={pending}>
          {pending ? <Spinner aria-hidden="true" data-icon="inline-start" /> : null}
          {t("add.newCode")}
        </Button>
      </DialogFooter>
    </form>
  );
}
