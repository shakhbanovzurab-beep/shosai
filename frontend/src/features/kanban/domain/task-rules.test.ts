import { describe, expect, it } from "vitest";

import { leoFieldsAfter } from "./task-rules";
import type { LeoField } from "./tasks-contract";

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
