import type { MessengerLink, MessengerLinksResponse } from "@/features/identity/domain/messenger-links-contract";

import type { ChatConnection } from "../domain/contract";
import type { SlackInstallation } from "../domain/slack-contract";

/*
 * Подсказка на главной пространства (CF-D9): подтвердить предложенный аккаунт Slack, если в пространстве работает
 * канал того же пространства Slack, или привязать Telegram, если работает группа Telegram, а Telegram у человека
 * не привязан. Закрытая раз, она не показывается этому аккаунту больше нигде.
 */

export type LinkHint = { kind: "slack"; chat: string; link: MessengerLink } | { kind: "telegram"; chat: string };

const working = (chat: ChatConnection) => chat.state === "working";

/** Нужна ли подсказка вообще — до того как грузить чаты пространства. */
export function mayHint({ items, hint_dismissed }: MessengerLinksResponse): boolean {
  if (hint_dismissed) return false;
  const proposed = items.some((link) => link.messenger === "slack" && link.state === "proposed");
  const telegram = items.some((link) => link.messenger === "telegram" && link.state === "linked");
  return proposed || !telegram;
}

export function linkHintFor(
  links: MessengerLinksResponse,
  chats: readonly ChatConnection[],
  installations: readonly SlackInstallation[],
): LinkHint | null {
  if (!mayHint(links)) return null;
  // Пространство Slack → работающий канал его установки в этом пространстве Shosai.
  const installationOf = new Map(installations.map((item) => [item.id, item.team.id]));
  const workingChannel = new Map<string, ChatConnection>();
  for (const chat of chats) {
    const team = chat.slack ? installationOf.get(chat.slack.installation_id) : undefined;
    if (team && working(chat) && !workingChannel.has(team)) workingChannel.set(team, chat);
  }
  for (const link of links.items) {
    if (link.messenger !== "slack" || link.state !== "proposed" || !link.space) continue;
    const chat = workingChannel.get(link.space.id);
    if (chat) return { kind: "slack", chat: chat.title, link };
  }
  if (links.items.some((link) => link.messenger === "telegram" && link.state === "linked")) return null;
  const group = chats.find((chat) => working(chat) && chat.messenger === "telegram");
  return group ? { kind: "telegram", chat: group.title } : null;
}
