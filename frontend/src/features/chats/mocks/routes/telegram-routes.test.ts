import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LUMEN } from "@/features/workspace/mocks/demo-lumen";

import { CODE_ALPHABET, type ConnectCode, type ConnectStatus, displayCode } from "../../domain/telegram-contract";
import { SUPPORT_CHAT } from "../seed/connections";
import { demo, resetDemo } from "../store/state";
import { connectCodeRoute, connectCodesRoute } from "./telegram-routes";
import { call, codeOf } from "./test-client";

const create = (body: unknown) => call(connectCodesRoute, "POST", "/codes", { params: { id: LUMEN }, body });
const poll = async (codeId: string) =>
  (await call(connectCodeRoute, "GET", "/code", { params: { id: LUMEN, codeId } })).body as ConnectStatus;

beforeEach(() => {
  resetDemo();
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
});

describe("Telegram connect codes", () => {
  it("gives a code of the unambiguous alphabet with its add links and command", async () => {
    const reply = await create({ project_id: null, mode: "mentions", data_notice_accepted: true });
    const code = reply.body as ConnectCode;
    expect(reply.status).toBe(201);
    expect([...code.code].every((c) => CODE_ALPHABET.includes(c))).toBe(true);
    expect(displayCode(code.code)).toMatch(/^[A-Z2-9]{4}-[A-Z2-9]{4}$/);
    expect(code.add_url).toBe(`https://t.me/${code.bot_username}?startgroup=${code.code}`);
    expect(code.add_as_admin_url.startsWith(`${code.add_url}&admin=`)).toBe(true);
    expect(code.command).toBe(`/connect@${code.bot_username} ${code.code}`);
  });

  it("refuses a code without the accepted data notice", async () => {
    const reply = await create({ project_id: null, mode: "all", data_notice_accepted: false });
    expect([reply.status, codeOf(reply)]).toEqual([422, "data_notice_required"]);
  });

  it("stays pending, then connects a group; Every message comes with the bot as admin", async () => {
    const code = (await create({ project_id: "leo-beta", mode: "all", data_notice_accepted: true }))
      .body as ConnectCode;
    expect((await poll(code.id)).status).toBe("pending");
    vi.advanceTimersByTime(3_000);
    const done = await poll(code.id);
    expect(done.status).toBe("connected");
    expect(done.connection?.binding).toEqual({ kind: "project", project: { id: "leo-beta", name: "Leo beta launch" } });
    expect([done.connection?.mode, done.connection?.state]).toEqual(["all", "working"]);
  });

  it("expires after its 30 minutes and voids the previous pending code", async () => {
    const first = (await create({ project_id: null, mode: "mentions", data_notice_accepted: true }))
      .body as ConnectCode;
    await create({ project_id: null, mode: "mentions", data_notice_accepted: true });
    expect((await poll(first.id)).status).toBe("expired");
    const second = [...demo().codes.values()].find((c) => c.status === "pending");
    vi.setSystemTime(Date.now() + 31 * 60_000);
    expect((await poll(second?.id ?? "")).status).toBe("expired");
  });

  it("reconnects the same chat and fixes its missing rights", async () => {
    const body = { project_id: null, mode: "all", data_notice_accepted: true, connection_id: SUPPORT_CHAT };
    const code = (await create(body)).body as ConnectCode;
    expect(code.connection_id).toBe(SUPPORT_CHAT);
    vi.advanceTimersByTime(3_000);
    const done = await poll(code.id);
    expect([done.connection?.id, done.connection?.state, done.connection?.problem]).toEqual([
      SUPPORT_CHAT,
      "working",
      null,
    ]);
  });

  it("cancels a code", async () => {
    const code = (await create({ project_id: null, mode: "mentions", data_notice_accepted: true })).body as ConnectCode;
    const cancelled = await call(connectCodeRoute, "DELETE", "/code", { params: { id: LUMEN, codeId: code.id } });
    expect(cancelled.status).toBe(204);
    vi.advanceTimersByTime(3_000);
    expect((await poll(code.id)).status).toBe("expired");
  });
});
