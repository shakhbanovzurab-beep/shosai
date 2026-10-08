/* Demo-only fixtures for the admin support inbox; imported by ./support-demo.ts, never by the client. */

import type { Conversation, SupportAttachment, SupportMessage, SupportUserProfile, Teammate } from "../domain/contract";

export const MINUTE = 60_000;
export const ago = (minutes: number) => new Date(Date.now() - minutes * MINUTE).toISOString();
export const now = () => new Date().toISOString();

export const ME: Teammate = { id: "tm-anna", name: "Анна Котова", avatar_url: null };
export const TEAMMATES: Teammate[] = [
  ME,
  { id: "tm-dmitry", name: "Дмитрий Орлов", avatar_url: null },
  { id: "tm-elena", name: "Елена Соколова", avatar_url: null },
  { id: "tm-igor", name: "Игорь Белов", avatar_url: null },
];
export const teammate = (id: string) => TEAMMATES.find((t) => t.id === id) ?? null;

export const USERS: SupportUserProfile[] = [
  {
    id: "u-pavel",
    name: "Павел Громов",
    email: "pavel.gromov@example.com",
    avatar_url: null,
    plan: "team",
    app_version: "Leo Web 2026.10.2",
    os: "Chrome 129 · macOS",
    signed_up_at: ago(60 * 24 * 410),
    recent_errors: 3,
  },
  {
    id: "u-olga",
    name: "Ольга Ветрова",
    email: "olga.vetrova@example.com",
    avatar_url: null,
    plan: "pro",
    app_version: "Leo для macOS 3.4.1",
    os: "macOS 15.1",
    signed_up_at: ago(60 * 24 * 95),
    recent_errors: 7,
  },
  {
    id: "u-sergey",
    name: "Сергей Лебедев",
    email: "s.lebedev@example.com",
    avatar_url: null,
    plan: "enterprise",
    app_version: "Leo Web 2026.10.2",
    os: "Firefox 131 · Windows 11",
    signed_up_at: ago(60 * 24 * 720),
    recent_errors: 0,
  },
  {
    id: "u-marina",
    name: "Марина Кузнецова",
    email: "marina.k@example.com",
    avatar_url: null,
    plan: "pro",
    app_version: "Leo для Windows 3.4.0",
    os: "Windows 11 23H2",
    signed_up_at: ago(60 * 24 * 40),
    recent_errors: 2,
  },
  {
    id: "u-artem",
    name: "Артём Новиков",
    email: "artem@novikov.studio",
    avatar_url: null,
    plan: "free",
    app_version: "Leo Web 2026.10.1",
    os: "Safari 18 · macOS",
    signed_up_at: ago(60 * 24 * 12),
    recent_errors: 0,
  },
  {
    id: "u-denis",
    name: "Денис Фролов",
    email: "denis.frolov@example.com",
    avatar_url: null,
    plan: "team",
    app_version: "Leo для macOS 3.4.1",
    os: "macOS 14.6",
    signed_up_at: ago(60 * 24 * 230),
    recent_errors: 12,
  },
  {
    id: "u-natalia",
    name: "Наталья Морозова",
    email: "n.morozova@example.com",
    avatar_url: null,
    plan: "pro",
    app_version: "Leo для Windows 3.3.8",
    os: "Windows 10 22H2",
    signed_up_at: ago(60 * 24 * 180),
    recent_errors: 1,
  },
];
export const userById = (id: string) => USERS.find((u) => u.id === id) ?? USERS[0];

export type ConversationRecord = Omit<Conversation, "user" | "last_message" | "assignee"> & {
  user_id: string;
  assignee_id: string | null;
  messages: SupportMessage[];
};

type Draft = Partial<SupportMessage> & Pick<SupportMessage, "author" | "body" | "created_at">;
export const msg = (m: Draft): SupportMessage => ({
  id: crypto.randomUUID(),
  kind: "reply",
  author_name: null,
  attachments: [],
  read_at: null,
  ...m,
});
export const file = (name: string, size_bytes: number, content_type: string): SupportAttachment => ({
  name,
  size_bytes,
  content_type,
  url: null,
});
