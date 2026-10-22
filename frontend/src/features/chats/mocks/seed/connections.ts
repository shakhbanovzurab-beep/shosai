import { LUMEN } from "@/features/workspace/mocks/demo-lumen";
import { NORTHWIND } from "@/features/workspace/mocks/demo-northwind";
import { ME } from "@/features/workspace/mocks/demo-people";

import type { Binding, ChatSettings } from "../../domain/contract";
import type { ChatsDemo, StoredConnection } from "../store/types";

/*
 * Подключённые чаты демо. Lumen — пространство, где демо-пользователь владелец: рабочие чаты и по одному на
 * каждую проблему. Northwind — пространство, где он участник: список только для чтения. Названия чатов
 * написали люди, поэтому они на одном языке во всех языках интерфейса.
 */

const HOUR = 3_600_000;
const DAY = 24 * HOUR;
export const ago = (ms: number) => new Date(Date.now() - ms).toISOString();

export const ARHAM = { user_id: ME.account, name: ME.name };
export const WORKSPACE: Binding = { kind: "workspace" };
export const project = (id: string, name: string): Binding => ({ kind: "project", project: { id, name } });

/** Ид seed-чатов, на которые ссылаются дайджесты и сценарий Leo. */
export const RELEASE_CHAT = "chat-tg-release";
export const SUPPORT_CHAT = "chat-tg-support";
export const PRICING_CHAT = "chat-sl-pricing";

type Seed = Pick<StoredConnection, "id" | "messenger" | "title" | "kind" | "binding" | "mode"> &
  Partial<StoredConnection>;

function connection(workspace_id: string, seed: Seed, joinedDaysAgo: number, messages: number): StoredConnection {
  const connected_at = ago(joinedDaysAgo * DAY);
  return {
    workspace_id,
    state: "working",
    problem: null,
    last_activity_at: messages > 0 ? ago(2 * HOUR) : null,
    history_from: connected_at,
    stored: { messages, oldest_at: messages > 0 ? connected_at : null },
    connected_at,
    connected_by: ARHAM,
    slack: null,
    bot_admin: seed.mode === "all",
    ...seed,
  };
}

const slack = (installation_id: string, channel_id: string) => ({ slack: { installation_id, channel_id } });

/** Чат демо. Название — позиционно: его написали люди, а не интерфейс. */
function chat(
  id: string,
  messenger: Seed["messenger"],
  name: string,
  kind: Seed["kind"],
  binding: Binding,
  mode: Seed["mode"],
  extra: Partial<StoredConnection> = {},
): Seed {
  return { id, messenger, title: name, kind, binding, mode, ...extra };
}

const LUMEN_CHATS: [Seed, number, number][] = [
  [
    chat(RELEASE_CHAT, "telegram", "Release team", "supergroup", project("leo-beta", "Leo beta launch"), "all"),
    18,
    1204,
  ],
  [
    chat("chat-tg-design", "telegram", "Design crit", "group", WORKSPACE, "mentions", { last_activity_at: ago(DAY) }),
    30,
    37,
  ],
  [
    chat(
      SUPPORT_CHAT,
      "telegram",
      "Support escalations",
      "supergroup",
      project("reliability", "Stream reliability"),
      "all",
      {
        state: "needs_attention",
        problem: "rights_missing",
        bot_admin: false,
      },
    ),
    3,
    48,
  ],
  [
    chat(
      PRICING_CHAT,
      "slack",
      "pricing",
      "public_channel",
      project("pricing", "Team plan pricing"),
      "all",
      slack("inst-lumen", "C07PRICING"),
    ),
    12,
    230,
  ],
  [
    chat("chat-sl-sales", "slack", "sales-team", "public_channel", WORKSPACE, "mentions", {
      state: "needs_attention",
      problem: "bot_not_in_chat",
      last_activity_at: ago(5 * DAY),
      ...slack("inst-lumen", "C07SALES"),
    }),
    20,
    9,
  ],
  [
    chat("chat-sl-partners", "slack", "partners-shared", "private_channel", WORKSPACE, "all", {
      state: "needs_attention",
      problem: "token_expired",
      last_activity_at: ago(9 * DAY),
      ...slack("inst-partners", "C07PARTNERS"),
    }),
    40,
    512,
  ],
];

function settings(home: ChatSettings["home"]): ChatSettings {
  return {
    retention_days: 90,
    home,
    messengers: [
      { messenger: "telegram", bot_username: "ShosaiLeoBot" },
      { messenger: "slack", app_name: "Leo" },
    ],
    limits: { connections: 50 },
  };
}

export function seedConnections(demo: ChatsDemo) {
  demo.settings.set(LUMEN, settings("eu"));
  demo.settings.set(NORTHWIND, settings("ru"));
  for (const [seed, days, messages] of LUMEN_CHATS)
    demo.connections.set(seed.id, connection(LUMEN, seed, days, messages));
  const pilot = connection(
    NORTHWIND,
    chat(
      "chat-tg-pilot",
      "telegram",
      "Northwind × Lumen pilot",
      "supergroup",
      project("pilot", "Pilot rollout"),
      "all",
    ),
    20,
    318,
  );
  demo.connections.set(pilot.id, { ...pilot, connected_by: { user_id: "u-liam", name: "Liam Turner" } });
}
