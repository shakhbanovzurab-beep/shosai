import { describe, expect, it, vi } from "vitest";

import { createPollingResource } from "./polling-resource";

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

describe("createPollingResource", () => {
  it("loads when the first component subscribes", async () => {
    const load = vi.fn(async () => "fresh");
    const resource = createPollingResource(load);

    const unsubscribe = resource.subscribe(() => undefined);
    await settle();

    expect(load).toHaveBeenCalledTimes(1);
    expect(resource.getSnapshot()).toEqual({ status: "ready", data: "fresh", refreshing: false });
    unsubscribe();
  });

  it("does not load again for data a route loader seeded, and loads on the next subscription", async () => {
    const load = vi.fn(async () => "fresh");
    const resource = createPollingResource(load);
    resource.seed("seeded");

    const first = resource.subscribe(() => undefined);
    await settle();
    expect(load).not.toHaveBeenCalled();
    expect(resource.getSnapshot()).toEqual({ status: "ready", data: "seeded", refreshing: false });
    first();

    const again = resource.subscribe(() => undefined);
    await settle();
    expect(load).toHaveBeenCalledTimes(1);
    again();
  });

  it("reloads with a read that starts after the call, even while another is in flight", async () => {
    let calls = 0;
    const load = vi.fn(async () => {
      calls += 1;
      return `read ${calls}`;
    });
    const resource = createPollingResource(load);
    const unsubscribe = resource.subscribe(() => undefined);

    await resource.reload();

    expect(load).toHaveBeenCalledTimes(2);
    expect(resource.getSnapshot()).toEqual({ status: "ready", data: "read 2", refreshing: false });
    unsubscribe();
  });
});
