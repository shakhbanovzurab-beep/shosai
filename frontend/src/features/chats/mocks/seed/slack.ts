import { LUMEN } from "@/features/workspace/mocks/demo-lumen";

import type { ChatsDemo, StoredInstallation } from "../store/types";
import { ARHAM, ago } from "./connections";

/*
 * Установки Slack демо: рабочая «Lumen» с каналами и «Lumen Partners», у которой кончился доступ. Каналы —
 * то, что отдал бы Slack: открытые и закрытые, в которых Leo уже есть.
 */

const DAY = 86_400_000;

function installation(
  id: string,
  name: string,
  domain: string,
  state: StoredInstallation["state"],
): StoredInstallation {
  return {
    id,
    workspace_id: LUMEN,
    domain,
    team: { id: `T-${id}`, name, icon_url: null },
    installed_at: ago(40 * DAY),
    installed_by: ARHAM,
    state,
    connections: 0,
  };
}

type Channel = [id: string, name: string, members: number, priv: boolean, leo: boolean];

const LUMEN_CHANNELS: Channel[] = [
  ["C07GENERAL", "general", 42, false, false],
  ["C07PRICING", "pricing", 9, false, true],
  ["C07SALES", "sales-team", 7, false, false],
  ["C07DESIGN", "design", 12, false, false],
  ["C07ENG", "engineering", 18, false, false],
  ["C07RANDOM", "random", 40, false, false],
  ["C07LEADS", "leadership", 5, true, true],
  ["C07INCIDENTS", "incidents", 9, true, true],
];

const PARTNER_CHANNELS: Channel[] = [["C07PARTNERS", "partners-shared", 14, true, true]];

const channels = (rows: Channel[]) =>
  rows.map(([id, name, member_count, priv, leo]) => ({ id, name, member_count, private: priv, leo_in_channel: leo }));

export function seedSlack(demo: ChatsDemo) {
  for (const item of [
    installation("inst-lumen", "Lumen", "lumen", "working"),
    installation("inst-partners", "Lumen Partners", "lumenpartners", "token_expired"),
  ])
    demo.installations.set(item.id, item);
  demo.channels.set("inst-lumen", channels(LUMEN_CHANNELS));
  demo.channels.set("inst-partners", channels(PARTNER_CHANNELS));
}

/** Каналы для новой установки, которую «ставят» через демо-согласие. */
export const NEW_TEAM_CHANNELS = channels([
  ["C08GENERAL", "general", 16, false, false],
  ["C08LAUNCH", "launch", 8, false, false],
  ["C08OPS", "ops", 6, false, false],
]);
