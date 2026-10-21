import { describe, expect, it } from "vitest";

import { leoFieldsAfter, movedTo, withCounts } from "./task-rules";
import type { LeoField, TaskDetail } from "./tasks-contract";

const ALL: LeoField[] = ["assignee", "due", "priority"];

describe("Leo's marks after a change", () => {
  it("drops the mark of the field the person changed", () => {
    expect(leoFieldsAfter(ALL, { assignee_name: "Maya" })).toEqual(["due", "priority"]);
    expect(leoFieldsAfter(ALL, { assignee_id: "u-1" })).toEqual(["due", "priority"]);
    expect(leoFieldsAfter(ALL, { priority: "low" })).toEqual(["assignee", "due"]);
  });

  it("treats either end of a range as a change of the deadline", () => {
    expect(leoFieldsAfter(ALL, { starts_on: "2026-10-01" })).toEqual(["assignee", "priority"]);
    expect(leoFieldsAfter(ALL, { due_on: "2026-10-02" })).toEqual(["assignee", "priority"]);
  });

  it("counts clearing a field as changing it", () => {
    expect(leoFieldsAfter(ALL, { assignee_name: null, due_on: null, priority: null })).toEqual([]);
  });

  it("keeps every mark when other fields change", () => {
    expect(leoFieldsAfter(ALL, { title: "Renamed", description: "More", recurrence: { every: "day" } })).toEqual(ALL);
  });
});

describe("a task's lists", () => {
  const list = ["a", "b", "c", "d"].map((id) => ({ id }));
  const ids = (items: { id: string }[]) => items.map((item) => item.id).join("");

  it("moves an item to a place, as the API's position counts it", () => {
    expect(ids(movedTo(list, "a", 2))).toBe("bcad");
    expect(ids(movedTo(list, "d", 0))).toBe("dabc");
    expect(ids(movedTo(list, "b", 99))).toBe("acdb");
    expect(ids(movedTo(list, "x", 1))).toBe("abcd");
  });

  it("counts the card's progress and attachments from the task's lists", () => {
    const detail = {
      subtasks: [
        { id: "s1", title: "One", done: true },
        { id: "s2", title: "Two", done: false },
      ],
      attachments: [],
      subtasks_done: 0,
      subtasks_total: 0,
      attachment_count: 3,
    } as unknown as TaskDetail;
    expect(withCounts(detail)).toMatchObject({ subtasks_done: 1, subtasks_total: 2, attachment_count: 0 });
  });
});
