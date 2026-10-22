import { apiRequest, jsonBody } from "@/lib/api/request";

import type { LinkRequest, MessengerLink, MessengerLinksResponse } from "../domain/messenger-links-contract";

/*
 * Аккаунты мессенджеров человека на `/v1/me/messenger-links*` (chats §1.2, identity шаг 18). Пока маршрутов нет в
 * сгенерированной схеме, их отдают моки identity; потом шлюз переходит на сгенерированный клиент.
 */

const base = "/v1/me/messenger-links";
const part = encodeURIComponent;

export const messengerLinksApi = {
  list: () => apiRequest<MessengerLinksResponse>(base),
  /** Подсказка о привязке больше не показывается этому аккаунту нигде (CF-D9). */
  dismissHint: () => apiRequest<void>(`${base}/hint-dismissal`, jsonBody("POST")),
  startTelegram: () => apiRequest<LinkRequest>(`${base}/telegram`, jsonBody("POST")),
  request: (id: string) => apiRequest<LinkRequest>(`${base}/telegram/requests/${part(id)}`),
  confirm: (id: string) => apiRequest<MessengerLink>(`${base}/${part(id)}/confirm`, jsonBody("POST")),
  /** Отвязать аккаунт или ответить «Это не я» на предложение Slack. */
  remove: (id: string) => apiRequest<void>(`${base}/${part(id)}`, jsonBody("DELETE")),
};
