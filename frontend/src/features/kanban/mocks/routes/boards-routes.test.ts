import { beforeEach, describe, expect, it } from "vitest";

import type { BoardDetail, BoardsResponse, ColumnHead } from "../../domain/boards-contract";
import { nextDue } from "../../domain/recurrence";
import type { Card } from "../../domain/tasks-contract";
import { DEFAULT_STOPWATCH_AUTOMATIONS } from "../../domain/time-contract";
import { today } from "../seed/builders";
import { resetDemo } from "../store/state";
import { boardRoute, boardsRoute, incomingRoute } from "./boards-routes";
import { cardRoute, columnRoute, columnsRoute } from "./columns-cards-routes";
import { call, codeOf } from "./test-client";

const board = async (id: string) =>
  (await call(boardRoute, "GET", `/v1/boards/${id}`, { params: { id } })).body as BoardDetail;
const column = (detail: BoardDetail, id: string) => detail.columns.find((c) => c.id === id);
const ids = (cards: Card[] | undefined) => (cards ?? []).map((c) => c.id);

beforeEach(() => {
  resetDemo();
});

describe("boards", () => {
  it("lists the boards and the incoming tasks that wait for a board", async () => {
    const { status, body } = await call(boardsRoute, "GET", "/v1/boards");
    const response = body as BoardsResponse;
    expect(status).toBe(200);
    expect(response.items.map((b) => b.id)).toEqual(expect.arrayContaining(["work", "home", "romashka"]));
    expect(response.incoming.board_id).toBeNull();
    expect(response.incoming.open).toBeGreaterThanOrEqual(2);
  });

  it("answers a board with its fields in order and the cards' own data", async () => {
    const work = await board("work");
    expect(work.stickers.map((s) => s.id)).toEqual([
      "assignee",
      "due",
      "priority",
      "recurrence",
      "stopwatch",
      "timer",
      "time_tracking",
      "st-type",
      "st-estimate",
      "st-customer",
    ]);
    expect(work.stickers.find((s) => s.id === "stopwatch")?.automations).toEqual(DEFAULT_STOPWATCH_AUTOMATIONS);
    expect(column(work, "planned")?.color).toBe("blue");
    const schema = column(work, "building")?.cards.find((c) => c.id === "w-schema");
    expect(schema).toMatchObject({ subtasks_done: 2, subtasks_total: 3, comment_count: 2, attachment_count: 2 });
    expect(schema?.cover?.attachment_id).toBe("w-schema-a1");
    expect(schema?.values["st-estimate"]).toEqual({ number: 4 });
    const deck = column(work, "planned")?.cards.find((c) => c.id === "w-pricing-deck");
    expect(deck?.leo_fields).toEqual(["assignee", "due", "priority"]);
  });

  it("refuses an unknown board in the platform's envelope", async () => {
    const reply = await call(boardRoute, "GET", "/v1/boards/nope", { params: { id: "nope" } });
    expect(reply.status).toBe(404);
    expect(codeOf(reply)).toBe("board_not_found");
  });

  it("lands incoming tasks once, on top of the first column of their kind", async () => {
    const set = await call(incomingRoute, "PUT", "/v1/boards/incoming", { body: { board_id: "work" } });
    expect((set.body as BoardsResponse).incoming.board_id).toBe("work");
    const first = await board("work");
    const top = ids(column(first, "ideas")?.cards);
    expect(top).toEqual(expect.arrayContaining(["m-hiring-plan", "m-venue"]));
    const spaces = first.columns.flatMap((c) => c.cards).filter((c) => c.space !== null);
    expect(spaces.length).toBeGreaterThan(0);
    expect(spaces.every((c) => !c.id.startsWith("ws:") && !c.can_delete)).toBe(true);
    const again = await board("work");
    expect(ids(column(again, "ideas")?.cards).filter((id) => id === "m-venue")).toHaveLength(1);
  });
});

describe("columns", () => {
  it("creates a column where asked and keeps its colour", async () => {
    const reply = await call(columnsRoute, "POST", "/v1/boards/home/columns", {
      params: { id: "home" },
      body: { title: "Waiting", kind: "in_progress", position: 1, color: "teal" },
    });
    expect(reply.status).toBe(201);
    const created = reply.body as ColumnHead;
    expect((await board("home")).columns[1]).toMatchObject({ id: created.id, color: "teal", collapsed: false });
  });

  it("hands a deleted column's cards to the first other column of its kind, in their order", async () => {
    const before = ids(column(await board("work"), "planned")?.cards);
    const ideas = ids(column(await board("work"), "ideas")?.cards);
    const reply = await call(columnRoute, "DELETE", "/v1/boards/work/columns/planned", {
      params: { id: "work", columnId: "planned" },
    });
    expect(reply.status).toBe(204);
    expect(ids(column(await board("work"), "ideas")?.cards)).toEqual([...before, ...ideas]);
  });

  it("keeps the last column of a kind", async () => {
    const reply = await call(columnRoute, "DELETE", "/v1/boards/work/columns/shipped", {
      params: { id: "work", columnId: "shipped" },
    });
    expect(reply.status).toBe(409);
    expect(codeOf(reply)).toBe("last_column_of_kind");
  });

  it("collapses and recolours a column", async () => {
    const reply = await call(columnRoute, "PATCH", "/v1/boards/work/columns/qa", {
      params: { id: "work", columnId: "qa" },
      body: { collapsed: true, color: null },
    });
    expect(reply.body).toMatchObject({ id: "qa", collapsed: true, color: null });
  });
});

describe("cards", () => {
  it("moves a card to a done column, and a recurring one comes back on its schedule once", async () => {
    const move = () =>
      call(cardRoute, "PATCH", "/v1/boards/work/cards/w-release-notes", {
        params: { id: "work", taskId: "w-release-notes" },
        body: { column_id: "shipped", position: 0 },
      });
    const done = await move();
    expect((done.body as Card).status).toBe("done");
    const work = await board("work");
    const next = column(work, "ideas")?.cards[0];
    expect(next?.title).toBe("Weekly release notes");
    expect(next?.recurring).toBe(true);
    const due = nextDue({ every: "week", weekdays: ["fri"] }, column(work, "shipped")?.cards[0]?.due_on ?? "", today());
    expect(next?.due_on).toBe(due);
    await move();
    const titles = (await board("work")).columns.flatMap((c) => c.cards).map((c) => c.title);
    expect(titles.filter((t) => t === "Weekly release notes")).toHaveLength(2);
  });

  it("refuses a move without its position", async () => {
    const reply = await call(cardRoute, "PATCH", "/v1/boards/work/cards/w-schema", {
      params: { id: "work", taskId: "w-schema" },
      body: { column_id: "qa" },
    });
    expect(reply.status).toBe(422);
    expect(codeOf(reply)).toBe("validation_error");
  });
});
