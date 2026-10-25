import { describe, expect, it, vi } from "vitest";

import { createPollingResource } from "./polling-resource";
import { inDomain, refreshDomains } from "./resource-domains";

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

describe("resources by data domain", () => {
  it("re-reads only the shown resources of a changed domain", async () => {
    const shownLoad = vi.fn(async () => "board");
    const hiddenLoad = vi.fn(async () => "task");
    const otherLoad = vi.fn(async () => "file");
    const shown = inDomain("tasks", createPollingResource(shownLoad));
    const hidden = inDomain("tasks", createPollingResource(hiddenLoad));
    const other = inDomain("files", createPollingResource(otherLoad));
    const stopShown = shown.subscribe(() => undefined);
    const stopOther = other.subscribe(() => undefined);
    await settle();

    refreshDomains(["tasks", "tasks", "calendar"]);
    await settle();

    expect(hidden.getSnapshot().status).toBe("loading");
    expect([shownLoad.mock.calls.length, hiddenLoad.mock.calls.length, otherLoad.mock.calls.length]).toEqual([2, 0, 1]);
    stopShown();
    stopOther();
  });
});
