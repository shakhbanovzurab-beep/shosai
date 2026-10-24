import { describe, expect, it } from "vitest";

import { pageSubject } from "./page-subject";

const id = "01a16f79-0883-72b4-b148-e11e76cbcd3b";

describe("what a page shows Leo", () => {
  it("names a meeting, a card and a board by their ids", () => {
    expect(pageSubject(`/app/notes/${id}`, "")).toEqual({ kind: "meeting", id });
    expect(pageSubject(`/app/w/acme/meetings/${id.toUpperCase()}`, "")).toEqual({ kind: "meeting", id });
    expect(pageSubject("/app/kanban", `?board=b&task=${id}`)).toEqual({ kind: "task", id });
    expect(pageSubject("/app/kanban", `board=${id}`)).toEqual({ kind: "board", id });
  });

  it("names nothing a page does not show, or an id that is not one", () => {
    expect(pageSubject("/app/kanban", "")).toBeNull();
    expect(pageSubject("/app/notes/drafts", "")).toBeNull();
    expect(pageSubject("/app/kanban", "?task=<script>")).toBeNull();
    expect(pageSubject("/app/dashboard", `?task=${id}`)).toBeNull();
  });
});
