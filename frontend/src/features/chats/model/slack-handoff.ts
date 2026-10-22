"use client";

import { useEffect, useRef, useState } from "react";

import { toast } from "sonner";

import { isChatsOAuthMessage } from "../domain/slack-contract";
import { chatResources } from "./resources";
import { type ApiWords, type ConnectWords, describeProblem } from "./words";

/*
 * Установка или переподключение Slack в окне поверх кабинета (OAuth, передачу ведёт connectors). Окно
 * открывается прямо по нажатию — браузеры блокируют окна, открытые позже, — и получает адрес согласия, как
 * только его вернёт сервер; итог приходит сообщением со страницы `/oauth/callback?flow=chats`.
 */

const POPUP = "popup,width=520,height=700";

export function useSlackHandoff(
  workspaceId: string,
  words: { t: ConnectWords; ta: ApiWords },
  onConnected: (installationId: string) => void,
) {
  const [waiting, setWaiting] = useState(false);
  const cleanup = useRef<(() => void) | null>(null);
  // Окно и слушатель живут дольше нажатия: при уходе экрана их надо снять.
  useEffect(() => () => cleanup.current?.(), []);

  const finish = () => {
    cleanup.current?.();
    cleanup.current = null;
    setWaiting(false);
  };

  const listen = (popup: Window) => {
    const onMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin || !isChatsOAuthMessage(event.data)) return;
      finish();
      const resources = chatResources(workspaceId);
      void resources.installations.reload();
      void resources.connections.reload();
      resources.forgetChannels();
      const { status, installation_id: installationId, error } = event.data;
      if (status === "connected" && installationId) onConnected(installationId);
      else if (status === "denied") toast(words.t("slack.denied"));
      else
        toast.error(words.t("slack.failed"), {
          description: error === "authorization_expired" ? words.t("slack.expired") : undefined,
        });
    };
    const closed = window.setInterval(() => {
      if (popup.closed) finish();
    }, 500);
    window.addEventListener("message", onMessage);
    cleanup.current = () => {
      window.removeEventListener("message", onMessage);
      window.clearInterval(closed);
    };
  };

  const start = async (installationId?: string) => {
    if (waiting) return;
    setWaiting(true);
    const popup = window.open("", "shosai-slack-oauth", POPUP);
    try {
      const { authorize_url: url } = await chatResources(workspaceId).api.beginSlack(
        installationId ? { installation_id: installationId } : {},
      );
      if (!popup) {
        // Окна заблокированы: согласие в этой вкладке, `/oauth/callback` вернёт человека в кабинет.
        window.location.assign(url);
        return;
      }
      popup.location.href = url;
      popup.focus();
      listen(popup);
    } catch (error) {
      popup?.close();
      setWaiting(false);
      toast.error(words.ta("title"), { description: describeProblem(error, words.ta) });
    }
  };

  return { waiting, start };
}
