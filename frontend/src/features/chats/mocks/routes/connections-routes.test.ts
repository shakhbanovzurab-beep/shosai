import { beforeEach, describe, expect, it } from "vitest";

import { LUMEN } from "@/features/workspace/mocks/demo-lumen";
import { NORTHWIND } from "@/features/workspace/mocks/demo-northwind";

import type { ChatConnection, ChatConnectionsPage, ChatSettings } from "../../domain/contract";
import { RELEASE_CHAT, SUPPORT_CHAT } from "../seed/connections";
import { RELEASE_DIGEST } from "../seed/digests";
import { resetDemo } from "../store/state";
import { connectionRoute, connectionsRoute, rejoinRoute, settingsRoute } from "./connections-routes";
import { digestRoute } from "./digest-routes";
import { call, codeOf } from "./test-client";

const list = async (id = LUMEN) =>
  (await call(connectionsRoute, "GET", `/v1/workspaces/${id}/chats`, { params: { id } })).body as ChatConnectionsPage;
const patch = (chatId: string, body: unknown, id = LUMEN) =>
  call(connectionRoute, "PATCH", `/v1/workspaces/${id}/chats/${chatId}`, { params: { id, chatId }, body });

beforeEach(() => {
  resetDemo();
});

describe("chats settings and list", () => {
  it("answers the served messengers, the data home and the retention", async () => {
    const { status, body } = await call(settingsRoute, "GET", "/v1/workspaces/x/chats/settings", {
      params: { id: LUMEN },
    });
    const settings = body as ChatSettings;
    expect(status).toBe(200);
    expect(settings.messengers.map((m) => m.messenger)).toEqual(["telegram", "slack"]);
    expect(settings.home).toBe("eu");
    expect(settings.retention_days).toBe(90);
  });

  it("puts the chats that need attention first, each with exactly one problem", async () => {
    const { items } = await list();
    const firstWorking = items.findIndex((c) => c.state === "working");
    expect(items.slice(0, firstWorking).every((c) => c.state === "needs_attention")).toBe(true);
    expect(items.slice(firstWorking).every((c) => c.state === "working")).toBe(true);
    expect(items.every((c) => (c.problem === null) === (c.state === "working"))).toBe(true);
    expect(new Set(items.map((c) => c.problem))).toEqual(
      new Set([null, "rights_missing", "bot_not_in_chat", "token_expired"]),
    );
  });

  it("lets a member read but not change, and hides a workspace from a non-member", async () => {
    expect((await list(NORTHWIND)).items).toHaveLength(1);
    const refused = await patch("chat-tg-pilot", { mode: "mentions" }, NORTHWIND);
    expect([refused.status, codeOf(refused)]).toEqual([403, "not_workspace_admin"]);
    const stranger = await call(connectionsRoute, "GET", "/v1/workspaces/ws-x/chats", { params: { id: "ws-x" } });
    expect([stranger.status, codeOf(stranger)]).toEqual([404, "workspace_not_found"]);
  });

  it("refuses a retention outside the three choices", async () => {
    const reply = await call(settingsRoute, "PATCH", "/v1/workspaces/x/chats/settings", {
      params: { id: LUMEN },
      body: { retention_days: 60 },
    });
    expect([reply.status, codeOf(reply)]).toEqual([422, "retention_invalid"]);
  });
});

describe("changing a chat", () => {
  it("needs the data notice to read every message, and then the bot as a Telegram admin (CF-D1)", async () => {
    const design = "chat-tg-design";
    const without = await patch(design, { mode: "all" });
    expect([without.status, codeOf(without)]).toEqual([422, "data_notice_required"]);
    const changed = (await patch(design, { mode: "all", data_notice_accepted: true })).body as ChatConnection;
    expect([changed.mode, changed.state, changed.problem]).toEqual(["all", "needs_attention", "rights_missing"]);
    const back = (await patch(design, { mode: "mentions" })).body as ChatConnection;
    expect([back.state, back.problem]).toEqual(["working", null]);
  });

  it("binds to a project of the workspace or to the whole workspace", async () => {
    const bound = (await patch(SUPPORT_CHAT, { project_id: "pricing" })).body as ChatConnection;
    expect(bound.binding).toEqual({ kind: "project", project: { id: "pricing", name: "Team plan pricing" } });
    const whole = (await patch(SUPPORT_CHAT, { project_id: null })).body as ChatConnection;
    expect(whole.binding).toEqual({ kind: "workspace" });
    const missing = await patch(SUPPORT_CHAT, { project_id: "nope" });
    expect([missing.status, codeOf(missing)]).toEqual([422, "project_not_found"]);
  });

  it("erases the chat's digests with the chat", async () => {
    const params = { id: LUMEN, chatId: RELEASE_CHAT, digestId: RELEASE_DIGEST };
    expect((await call(digestRoute, "GET", "/digest", { params })).status).toBe(200);
    const gone = await call(connectionRoute, "DELETE", "/chat", { params: { id: LUMEN, chatId: RELEASE_CHAT } });
    expect(gone.status).toBe(204);
    const after = await call(digestRoute, "GET", "/digest", { params });
    expect([after.status, codeOf(after)]).toEqual([404, "digest_not_found"]);
  });

  it("brings Leo back to a public Slack channel only", async () => {
    const back = await call(rejoinRoute, "POST", "/rejoin", { params: { id: LUMEN, chatId: "chat-sl-sales" } });
    expect((back.body as ChatConnection).state).toBe("working");
    const refused = await call(rejoinRoute, "POST", "/rejoin", { params: { id: LUMEN, chatId: RELEASE_CHAT } });
    expect([refused.status, codeOf(refused)]).toEqual([409, "rejoin_unsupported"]);
  });
});
