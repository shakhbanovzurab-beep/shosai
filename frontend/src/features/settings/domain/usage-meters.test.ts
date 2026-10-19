import { describe, expect, it } from "vitest";

import { frontierStanding, meterStanding, worstTone } from "./usage-meters";

describe("usage meters", () => {
  it("tell ok, running low from 80% and used up, with the bar's share", () => {
    expect(meterStanding(50, 100)).toEqual({ share: 0.5, tone: "ok" });
    expect(meterStanding(80, 100)).toEqual({ share: 0.8, tone: "low" });
    expect(meterStanding(130, 100)).toEqual({ share: 1, tone: "full" });
  });

  it("draw no bar without a limit", () => {
    expect(meterStanding(10_000, null)).toEqual({ share: null, tone: "ok" });
  });

  it("keep frontier models running low, not stopped, while bought tokens last", () => {
    expect(frontierStanding(100, 100, 5_000).tone).toBe("low");
    expect(frontierStanding(100, 100, 0).tone).toBe("full");
  });

  it("speak with the most pressing tone of the rows", () => {
    expect(worstTone(["ok", "low", "ok"])).toBe("low");
    expect(worstTone(["low", "full"])).toBe("full");
    expect(worstTone([])).toBe("ok");
  });
});
