import { describe, expect, it } from "vitest";

import type { StorageStanding } from "@/features/file-manager/domain/contract";
import type { PlansResponse } from "@/features/upgrade/domain/contract";

import type { Usage } from "../domain/billing-contract";
import { usageRows } from "./usage-overview";

const usage: Usage = {
  week_start: "2026-10-12T00:00:00Z",
  resets_at: "2026-10-19T00:00:00Z",
  limits: [
    { tier: "standard", used_tokens: 900, limit_tokens: 1_000 },
    { tier: "frontier", used_tokens: 500, limit_tokens: 500 },
  ],
  frontier: { extra_tokens: 2_000, models: [], packs: [] },
};

const plans = {
  usage: { used_minutes: 30, limit_minutes: 120, resets_at: "2026-11-01T00:00:00Z" },
} as PlansResponse;

const storage: StorageStanding = {
  used_bytes: 10,
  limit_bytes: null,
  over_limit_since: null,
  removal_at: null,
  leo_used_bytes: 0,
  leo_limit_bytes: 0,
  leo_over_limit_since: null,
  leo_removal_at: null,
};

describe("the usage overview's rows", () => {
  it("come in order: tokens, minutes, storage, leaving out what the plan doesn't include", () => {
    const rows = usageRows({ usage, plans, storage });

    expect(rows.map((row) => [row.kind, row.tone])).toEqual([
      ["standard", "low"],
      ["frontier", "low"],
      ["minutes", "ok"],
      ["storage", "ok"],
    ]);
    expect(rows.find((row) => row.kind === "storage")?.share).toBeNull();
  });

  it("show only the sources that answered", () => {
    expect(usageRows({ usage: null, plans, storage: null }).map((row) => row.kind)).toEqual(["minutes"]);
    expect(usageRows({ usage: null, plans: null, storage: null })).toEqual([]);
  });
});
