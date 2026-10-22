"use client";

import { useEffect } from "react";

import { CircleCheck, CircleX } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Link } from "@/lib/navigation";

import { CHATS_OAUTH_MESSAGE_TYPE, type ChatsOAuthMessage, type SlackHandoffStatus } from "../../domain/slack-contract";

/*
 * Возврат из Slack (`/oauth/callback?flow=chats`): сообщает итог окну кабинета, которое открыло согласие, и
 * закрывается. Видна, только если окно открыли не всплывающим или браузер его оставил.
 */

export function ChatsOAuthCallback({
  status,
  installationId,
  error,
}: {
  status: SlackHandoffStatus;
  installationId: string | null;
  error: string | null;
}) {
  const t = useTranslations("chatsConnect");

  // Итог уходит окну-хозяину: это связь с внешним окном, а не реакция на действие человека.
  useEffect(() => {
    const opener = window.opener as Window | null;
    if (!opener || opener.closed) return;
    const message: ChatsOAuthMessage = {
      type: CHATS_OAUTH_MESSAGE_TYPE,
      status,
      installation_id: installationId,
      error,
    };
    opener.postMessage(message, window.location.origin);
    window.close();
  }, [status, installationId, error]);

  const Icon = status === "connected" ? CircleCheck : CircleX;
  return (
    <main className="flex min-h-dvh items-center justify-center bg-background p-6">
      <div className="flex max-w-sm flex-col items-center gap-3 text-center">
        <Icon className="size-10 text-muted-foreground" aria-hidden="true" />
        <h1 className="font-medium text-xl">{t(`slack.callback.${status}`)}</h1>
        {status === "error" ? (
          <p className="text-muted-foreground text-sm">
            {error === "authorization_expired" ? t("slack.expired") : t("slack.callback.errorHint")}
          </p>
        ) : null}
        <Button variant="outline" asChild>
          <Link href="/app">{t("slack.callback.back")}</Link>
        </Button>
      </div>
    </main>
  );
}
