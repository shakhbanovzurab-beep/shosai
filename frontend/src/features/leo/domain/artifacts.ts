/*
 * Артефакты ответа Leo (Leo §13.2, событие `artifact`): ссылка на результат, который читают отдельно.
 * `chat_digest` — дайджест командного чата (CF-D11, требование AG-R1 плана agent): поток несёт только ссылку,
 * сам дайджест хранит слайс chats 30 дней и стирает вместе с чатом.
 */

export type LeoArtifact = {
  kind: "chat_digest";
  /** Ид дайджеста. */
  ref: string;
  /** Подпись для тех, кто карточку не видит. */
  alt: string;
  workspace_id: string;
  chat_id: string;
};
