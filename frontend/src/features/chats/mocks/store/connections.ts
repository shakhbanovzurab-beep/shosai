import { activeMembership } from "@/features/workspace/mocks/demo-store";

import {
  type Binding,
  type ChatConnection,
  type ChatConnectionPatch,
  type ChatProblem,
  type ChatSettings,
  RETENTION_DAYS,
  type RetentionDays,
} from "../../domain/contract";
import { eraseDigestsOf } from "./digests";
import { fail, type Outcome, ok } from "./outcome";
import { demo } from "./state";
import type { StoredConnection } from "./types";

/* Подключения пространства: список, изменение привязки и режима, отключение, возврат Leo в канал Slack. */

/** Подключение в форме контракта: без того, что сервер держит для себя. */
export function connectionOf({ bot_admin: _admin, ...connection }: StoredConnection): ChatConnection {
  return connection;
}

/** Состояние по проблеме: «работает» ровно тогда, когда проблемы нет. */
export function withProblem(connection: StoredConnection, problem: ChatProblem | null) {
  connection.problem = problem;
  connection.state = problem ? "needs_attention" : "working";
}

/** Режиму «Каждое сообщение» в Telegram нужен бот-администратор (CF-D1). */
export function rightsProblem(connection: StoredConnection): ChatProblem | null {
  return connection.messenger === "telegram" && connection.mode === "all" && !connection.bot_admin
    ? "rights_missing"
    : null;
}

const time = (moment: string | null) => (moment ? Date.parse(moment) : Number.NEGATIVE_INFINITY);

/** Сначала те, что требуют внимания, потом по последней активности, без активности — в конце. */
export function connectionsOf(workspaceId: string): ChatConnection[] {
  return [...demo().connections.values()]
    .filter((connection) => connection.workspace_id === workspaceId)
    .toSorted(
      (a, b) =>
        Number(b.state === "needs_attention") - Number(a.state === "needs_attention") ||
        time(b.last_activity_at) - time(a.last_activity_at),
    )
    .map(connectionOf);
}

export function findConnection(workspaceId: string, id: string) {
  const connection = demo().connections.get(id);
  return connection?.workspace_id === workspaceId ? connection : null;
}

/** Привязка по `project_id`: null — всё пространство; проект должен быть в пространстве. */
export function bindingOf(workspaceId: string, projectId: string | null): Outcome<Binding> {
  if (projectId === null) return ok({ kind: "workspace" });
  const project = activeMembership(workspaceId)?.data.projects.find((p) => p.id === projectId);
  return project ? ok({ kind: "project", project: { id: project.id, name: project.name } }) : fail("project_not_found");
}

export function patchConnection(connection: StoredConnection, patch: ChatConnectionPatch): Outcome<ChatConnection> {
  if (patch.mode === "all" && connection.mode !== "all" && patch.data_notice_accepted !== true)
    return fail("data_notice_required");
  if (patch.project_id !== undefined) {
    const binding = bindingOf(connection.workspace_id, patch.project_id);
    if (!binding.ok) return binding;
    connection.binding = binding.value;
  }
  if (patch.mode) connection.mode = patch.mode;
  if (connection.problem === null || connection.problem === "rights_missing")
    withProblem(connection, rightsProblem(connection));
  return ok(connectionOf(connection));
}

/** Отключение: сообщения и дайджесты чата стираются, бот выходит из чата. */
export function disconnect(connection: StoredConnection) {
  demo().connections.delete(connection.id);
  eraseDigestsOf(connection.id);
}

/** Leo снова входит в открытый канал Slack, из которого его убрали. */
export function rejoin(connection: StoredConnection): Outcome<ChatConnection> {
  const { slack } = connection;
  if (!slack || connection.kind !== "public_channel" || connection.problem !== "bot_not_in_chat")
    return fail("rejoin_unsupported");
  const channel = demo()
    .channels.get(slack.installation_id)
    ?.find((c) => c.id === slack.channel_id);
  if (channel) channel.leo_in_channel = true;
  withProblem(connection, null);
  return ok(connectionOf(connection));
}

export const settingsOf = (workspaceId: string): ChatSettings | null => demo().settings.get(workspaceId) ?? null;

export function patchSettings(workspaceId: string, retention: number): Outcome<ChatSettings> {
  const settings = demo().settings.get(workspaceId);
  if (!settings) return fail("workspace_not_found");
  if (!(RETENTION_DAYS as readonly number[]).includes(retention)) return fail("retention_invalid");
  settings.retention_days = retention as RetentionDays;
  return ok(settings);
}
