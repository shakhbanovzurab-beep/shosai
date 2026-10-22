import { CONNECT_CODE_TTL_MS, CONNECTIONS_MAX } from "../../domain/contract";
import {
  CODE_ALPHABET,
  CODE_LENGTH,
  CONNECT_REFUSALS,
  type ConnectCode,
  type ConnectCodeCreate,
  type ConnectStatus,
} from "../../domain/telegram-contract";
import { ARHAM } from "../seed/connections";
import { bindingOf, connectionOf, findConnection, rightsProblem, withProblem } from "./connections";
import { fail, type Outcome, ok } from "./outcome";
import { demo, demoOutcome, now } from "./state";
import type { StoredCode, StoredConnection } from "./types";

/*
 * Коды подключения Telegram. В демо нет бота: код «срабатывает» при первом опросе спустя 3 с — группа из
 * списка ниже добавила бота и прислала код; переключатель демо даёт истечение, отказ или вход без прав.
 */

const BOT = "ShosaiLeoBot";
const JOIN_AFTER_MS = 3_000;
const GROUPS = ["Marketing sync", "Ops on call", "Founders"];

function generateCode() {
  const bytes = crypto.getRandomValues(new Uint8Array(CODE_LENGTH));
  return [...bytes].map((byte) => CODE_ALPHABET[byte % CODE_ALPHABET.length]).join("");
}

export const publicCode = ({
  workspace_id: _ws,
  created_at: _at,
  outcome: _o,
  status: _s,
  result_connection_id: _r,
  ...code
}: StoredCode): ConnectCode => code;

export function createCode(workspaceId: string, body: ConnectCodeCreate): Outcome<ConnectCode> {
  const d = demo();
  const reconnect = body.connection_id ? findConnection(workspaceId, body.connection_id) : null;
  if (body.connection_id && reconnect?.messenger !== "telegram") return fail("chat_not_found");
  const used = [...d.connections.values()].filter((c) => c.workspace_id === workspaceId).length;
  if (!reconnect && used >= CONNECTIONS_MAX) return fail("connections_full");
  const binding = bindingOf(workspaceId, body.project_id);
  if (!binding.ok) return binding;
  for (const code of d.codes.values())
    if (code.workspace_id === workspaceId && code.status === "pending") code.status = "expired";
  const value = generateCode();
  const switched = demoOutcome();
  const outcome = switched === "refuse" ? "chat_already_connected" : (switched ?? "connect");
  const code: StoredCode = {
    id: `code-${crypto.randomUUID()}`,
    code: value,
    expires_at: new Date(Date.now() + CONNECT_CODE_TTL_MS).toISOString(),
    bot_username: BOT,
    mode: body.mode,
    binding: binding.value,
    add_url: `https://t.me/${BOT}?startgroup=${value}`,
    add_as_admin_url: `https://t.me/${BOT}?startgroup=${value}&admin=pin_messages`,
    command: `/connect@${BOT} ${value}`,
    connection_id: reconnect?.id ?? null,
    workspace_id: workspaceId,
    created_at: Date.now(),
    outcome,
    status: "pending",
    result_connection_id: null,
  };
  d.codes.set(code.id, code);
  return ok(publicCode(code));
}

function joinedGroup(code: StoredCode): StoredConnection {
  const d = demo();
  const title = GROUPS[d.joined++ % GROUPS.length];
  const connected_at = now();
  const connection: StoredConnection = {
    id: `chat-tg-${crypto.randomUUID()}`,
    workspace_id: code.workspace_id,
    messenger: "telegram",
    title,
    kind: "supergroup",
    binding: code.binding,
    mode: code.mode,
    state: "working",
    problem: null,
    last_activity_at: null,
    history_from: connected_at,
    stored: { messages: 0, oldest_at: null },
    connected_at,
    connected_by: ARHAM,
    slack: null,
    bot_admin: false,
  };
  d.connections.set(connection.id, connection);
  return connection;
}

/** Код сработал: новая группа или та же, что переподключают. Для «Каждого сообщения» бот — администратор. */
function settle(code: StoredCode): StoredConnection {
  const existing = code.connection_id ? demo().connections.get(code.connection_id) : undefined;
  const connection = existing ?? joinedGroup(code);
  connection.bot_admin = code.mode === "all" && code.outcome !== "member";
  if (!existing) connection.mode = code.mode;
  withProblem(connection, rightsProblem(connection));
  return connection;
}

function statusOf(code: StoredCode): ConnectStatus {
  const connection = code.result_connection_id ? demo().connections.get(code.result_connection_id) : undefined;
  const refusal = code.status === "refused" ? (CONNECT_REFUSALS.find((r) => r === code.outcome) ?? null) : null;
  return { status: code.status, connection: connection ? connectionOf(connection) : null, refusal };
}

export function pollCode(workspaceId: string, codeId: string): Outcome<ConnectStatus> {
  const code = demo().codes.get(codeId);
  if (code?.workspace_id !== workspaceId) return fail("code_not_found");
  if (code.status === "pending" && Date.now() > Date.parse(code.expires_at)) code.status = "expired";
  if (code.status === "pending" && Date.now() - code.created_at >= JOIN_AFTER_MS) {
    if (code.outcome === "expire") code.status = "expired";
    else if (code.outcome === "connect" || code.outcome === "member") {
      code.result_connection_id = settle(code).id;
      code.status = "connected";
    } else code.status = "refused";
  }
  return ok(statusOf(code));
}

export function cancelCode(workspaceId: string, codeId: string): Outcome<null> {
  const code = demo().codes.get(codeId);
  if (code?.workspace_id !== workspaceId) return fail("code_not_found");
  if (code.status === "pending") code.status = "expired";
  return ok(null);
}
