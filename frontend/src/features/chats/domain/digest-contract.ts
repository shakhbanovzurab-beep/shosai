import type { Binding, Messenger } from "./contract";

/*
 * Дайджест чата — результат инструмента Leo `chats.digest` (chats §1.3, CF-D11): решения, открытые вопросы и
 * обещания за период, каждое со ссылкой на сообщение. Слова пунктов пишет модель на языке ответа человека;
 * цитаты — исходный текст сообщений. Хранится 30 дней и стирается вместе с чатом.
 */

export type ChatMessageRef = {
  id: string;
  author_name: string;
  sent_at: string;
  /** Текст сообщения, обрезанный до 280 знаков. */
  quote: string;
  /** Ссылка на сообщение в мессенджере; у обычной группы Telegram ссылок на сообщения нет. */
  url: string | null;
};

export type DigestItem = {
  id: string;
  text: string;
  message: ChatMessageRef;
  /** Карточка одобрения, сделанная из пункта. */
  proposal_id: string | null;
  /** Задача, которую создала одобренная карточка (агентское дополнение шага 1, §3.8 плана пакета). */
  task_id: string | null;
};

export type DigestPromise = DigestItem & {
  /** Участник, если имя сопоставилось; иначе имя, как его сказали. */
  who: { user_id: string | null; name: string };
  due_on: string | null;
  /** Срок словами, когда это не день: «к пятнице». */
  when_text: string | null;
};

export type ChatDigest = {
  id: string;
  chat: { id: string; workspace_id: string; messenger: Messenger; title: string; binding: Binding };
  period: { from: string; to: string };
  created_at: string;
  coverage: {
    history_from: string;
    messages_read: number;
    /** За период было больше 5 000 сообщений: прочитаны последние 5 000. */
    truncated: boolean;
  };
  decisions: DigestItem[];
  questions: DigestItem[];
  promises: DigestPromise[];
};

export type DigestSection = "decisions" | "questions" | "promises";

/** «Сделать задачей»: пункты дайджеста в одну карточку одобрения `tasks.create` (CF-D5). */
export type TaskProposalsCreate = { item_ids: string[] };

export const DIGEST_ITEMS_PER_PROPOSAL = 20;
export const DIGEST_MESSAGES_READ_MAX = 5_000;

/** Период начинается раньше, чем у Shosai есть сообщения чата. */
export const startsBeforeHistory = (digest: Pick<ChatDigest, "period" | "coverage">) =>
  Date.parse(digest.coverage.history_from) > Date.parse(digest.period.from);

/** Все пункты дайджеста по порядку разделов. */
export const digestItems = (digest: Pick<ChatDigest, DigestSection>): DigestItem[] => [
  ...digest.decisions,
  ...digest.questions,
  ...digest.promises,
];
