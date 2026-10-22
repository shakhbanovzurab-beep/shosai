import { beforeEach, describe, expect, it } from "vitest";

import type { BoardDetail } from "../../domain/boards-contract";
import type { TaskDetail } from "../../domain/tasks-contract";
import { resetDemo } from "../store/state";
import { boardRoute } from "./boards-routes";
import { taskRoute } from "./tasks-routes";
import { call } from "./test-client";

beforeEach(() => {
  resetDemo();
});

describe("a task from a team chat (TK-D13)", () => {
  it("shows its messenger and chat on the card face and the message link in the detail", async () => {
    const board = (await call(boardRoute, "GET", "/v1/boards/work", { params: { id: "work" } })).body as BoardDetail;
    const cards = board.columns.flatMap((column) => column.cards);
    const fromChat = cards.find((card) => card.id === "t-chat-checklist");
    expect(fromChat?.source_chat).toEqual({ messenger: "telegram", chat_title: "Release team" });
    expect(cards.filter((card) => card.source_chat === null).length).toBeGreaterThan(0);

    const reply = await call(taskRoute, "GET", "/v1/tasks/t-chat-checklist", { params: { id: "t-chat-checklist" } });
    const detail = reply.body as TaskDetail;
    expect(detail.source.kind).toBe("chat");
    expect(detail.source.chat?.message?.url).toMatch(/^https:\/\/t\.me\/c\/\d+\/\d+$/);
    expect(detail.space?.workspace_slug).toBe("lumen");
  });
});
