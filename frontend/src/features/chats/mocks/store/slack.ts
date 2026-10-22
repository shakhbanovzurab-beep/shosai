import { type ChatConnection, CONNECTIONS_MAX } from "../../domain/contract";
import type { SlackChannelsPage, SlackConnect, SlackHandoff, SlackInstallation } from "../../domain/slack-contract";
import { ARHAM } from "../seed/connections";
import { NEW_TEAM_CHANNELS } from "../seed/slack";
import { bindingOf, connectionOf, withProblem } from "./connections";
import { eraseDigestsOf } from "./digests";
import { fail, type Outcome, ok } from "./outcome";
import { demo, now } from "./state";
import type { StoredConnection, StoredInstallation } from "./types";

/*
 * Slack в демо: OAuth через страницу-заглушку согласия (`/oauth/demo-authorize?flow=chats`), установки, их
 * каналы и подключение пачкой. Настоящую передачу ведёт connectors; здесь — тот же контракт.
 */

const CONSENT_TTL_MS = 10 * 60_000;

const connectionsOfInstallation = (id: string) =>
  [...demo().connections.values()].filter((c) => c.slack?.installation_id === id);

export const installationOf = ({ workspace_id: _ws, domain: _d, ...item }: StoredInstallation): SlackInstallation => ({
  ...item,
  connections: connectionsOfInstallation(item.id).length,
});

export const installationsOf = (workspaceId: string) =>
  [...demo().installations.values()].filter((i) => i.workspace_id === workspaceId).map(installationOf);

function findInstallation(workspaceId: string, id: string) {
  const installation = demo().installations.get(id);
  return installation?.workspace_id === workspaceId ? installation : null;
}

export function beginHandoff(workspaceId: string, installationId: string | undefined): Outcome<SlackHandoff> {
  if (installationId && !findInstallation(workspaceId, installationId)) return fail("installation_not_found");
  const state = crypto.randomUUID();
  const expires_at = Date.now() + CONSENT_TTL_MS;
  demo().consents.set(state, { workspace_id: workspaceId, installation_id: installationId ?? null, expires_at });
  const params = new URLSearchParams({ connector: "slack", flow: "chats", state });
  return ok({ authorize_url: `/oauth/demo-authorize?${params}`, expires_at: new Date(expires_at).toISOString() });
}

/** Ответ экрана согласия: новая установка или переподключённая; итог — параметры страницы `/oauth/callback`. */
export function completeHandoff(state: string, approved: boolean): URLSearchParams {
  const d = demo();
  const consent = d.consents.get(state);
  d.consents.delete(state);
  if (!consent || consent.expires_at < Date.now())
    return new URLSearchParams({ flow: "chats", status: "error", error: "authorization_expired" });
  if (!approved) return new URLSearchParams({ flow: "chats", status: "denied" });
  const existing = consent.installation_id ? d.installations.get(consent.installation_id) : undefined;
  const installation = existing ?? newInstallation(consent.workspace_id);
  installation.state = "working";
  for (const connection of connectionsOfInstallation(installation.id))
    if (connection.problem === "token_expired") withProblem(connection, null);
  return new URLSearchParams({ flow: "chats", status: "connected", installation_id: installation.id });
}

function newInstallation(workspaceId: string): StoredInstallation {
  const d = demo();
  const id = `inst-${crypto.randomUUID()}`;
  const installation: StoredInstallation = {
    id,
    workspace_id: workspaceId,
    domain: "lumenlabs",
    team: { id: `T-${id}`, name: "Lumen Labs", icon_url: null },
    installed_at: now(),
    installed_by: ARHAM,
    state: "working",
    connections: 0,
  };
  d.installations.set(id, installation);
  d.channels.set(id, structuredClone(NEW_TEAM_CHANNELS));
  return installation;
}

export function removeInstallation(workspaceId: string, id: string): Outcome<null> {
  if (!findInstallation(workspaceId, id)) return fail("installation_not_found");
  for (const connection of connectionsOfInstallation(id)) {
    demo().connections.delete(connection.id);
    eraseDigestsOf(connection.id);
  }
  demo().installations.delete(id);
  return ok(null);
}

export function channelsPage(
  workspaceId: string,
  id: string,
  query: { q: string; cursor: string | null; limit: number },
): Outcome<SlackChannelsPage> {
  const installation = findInstallation(workspaceId, id);
  if (!installation) return fail("installation_not_found");
  if (installation.state === "token_expired") return fail("token_expired");
  const connected = new Map(connectionsOfInstallation(id).map((c) => [c.slack?.channel_id, c.id]));
  const needle = query.q.trim().toLocaleLowerCase();
  const all = (demo().channels.get(id) ?? [])
    .filter((channel) => channel.name.includes(needle))
    .toSorted((a, b) => a.name.localeCompare(b.name))
    .map((channel) => ({ ...channel, connection_id: connected.get(channel.id) ?? null }));
  const start = Number(query.cursor ?? 0);
  const end = start + query.limit;
  return ok({ items: all.slice(start, end), next_cursor: end < all.length ? String(end) : null });
}

export function connectChannels(workspaceId: string, body: SlackConnect): Outcome<ChatConnection[]> {
  const d = demo();
  const installation = findInstallation(workspaceId, body.installation_id);
  if (!installation) return fail("installation_not_found");
  if (installation.state === "token_expired") return fail("token_expired");
  const catalog = new Map((d.channels.get(installation.id) ?? []).map((c) => [c.id, c]));
  const taken = new Set(connectionsOfInstallation(installation.id).map((c) => c.slack?.channel_id));
  const already = body.channels.filter((c) => taken.has(c.channel_id)).map((c) => c.channel_id);
  if (already.length > 0) return fail("channel_already_connected", { channel_ids: already });
  const picked = body.channels.map((c) => ({ ...c, channel: catalog.get(c.channel_id) }));
  if (picked.some((p) => !p.channel || (p.channel.private && !p.channel.leo_in_channel)))
    return fail("leo_not_in_channel");
  const used = [...d.connections.values()].filter((c) => c.workspace_id === workspaceId).length;
  if (used + picked.length > CONNECTIONS_MAX) return fail("connections_full");
  const bindings = picked.map((p) => bindingOf(workspaceId, p.project_id));
  const missing = bindings.find((b) => !b.ok);
  if (missing && !missing.ok) return missing;
  const created = picked.map((p, index): StoredConnection => {
    const channel = p.channel as NonNullable<typeof p.channel>;
    channel.leo_in_channel = true;
    const binding = bindings[index];
    const connected_at = now();
    return {
      id: `chat-sl-${crypto.randomUUID()}`,
      workspace_id: workspaceId,
      messenger: "slack",
      title: channel.name,
      kind: channel.private ? "private_channel" : "public_channel",
      binding: binding.ok ? binding.value : { kind: "workspace" },
      mode: body.mode,
      state: "working",
      problem: null,
      last_activity_at: null,
      history_from: connected_at,
      stored: { messages: 0, oldest_at: null },
      connected_at,
      connected_by: ARHAM,
      slack: { installation_id: installation.id, channel_id: channel.id },
      bot_admin: false,
    };
  });
  for (const connection of created) d.connections.set(connection.id, connection);
  return ok(created.map(connectionOf));
}
