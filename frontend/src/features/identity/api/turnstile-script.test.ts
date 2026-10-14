import { describe, expect, it } from "vitest";

import { loadTurnstile, type ScriptHost, type TurnstileApi } from "./turnstile-script";

const API: TurnstileApi = { render: () => "w-1", remove: () => undefined };

/** A page whose script either loads, fails or never answers; timers run when the test says. */
function page(outcome: "loads" | "fails" | "hangs") {
  let loaded = false;
  const timers: (() => void)[] = [];
  const host: ScriptHost = {
    turnstile: () => (loaded ? API : undefined),
    appendScript(_src, onLoad, onError) {
      if (outcome === "loads") {
        loaded = true;
        onLoad();
      } else if (outcome === "fails") onError();
    },
    after(_ms, run) {
      timers.push(run);
      return () => timers.splice(timers.indexOf(run), 1);
    },
  };
  return {
    host,
    fireTimers: () => {
      for (const run of [...timers]) run();
    },
  };
}

describe("loadTurnstile", () => {
  it("gives the API once the script has loaded", async () => {
    await expect(loadTurnstile(page("loads").host)).resolves.toBe(API);
  });

  it("ends with an error when the script fails, and tries again next time", async () => {
    await expect(loadTurnstile(page("fails").host)).rejects.toThrow("turnstile_failed");
    await expect(loadTurnstile(page("loads").host)).resolves.toBe(API);
  });

  it("ends with an error when the script never answers", async () => {
    const hanging = page("hangs");
    const loading = loadTurnstile(hanging.host, 10);
    hanging.fireTimers();
    await expect(loading).rejects.toThrow("turnstile_timeout");
  });
});
