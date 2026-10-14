import { describe, expect, it } from "vitest";

import { socialRefusalPath, socialReturnOf } from "./social-return";

const of = (query: string) => socialReturnOf(new URLSearchParams(query));

describe("socialReturnOf", () => {
  it("reads the ticket the provider's callback put into the address", () => {
    expect(of("social=t-1&next=%2Fapp%2Fnotes")).toEqual({ kind: "session", ticket: "t-1" });
    expect(of("social_consent=t-2&social_provider=vk")).toEqual({ kind: "consent", ticket: "t-2", provider: "vk" });
  });

  it("turns a refusal into a problem the form can word", () => {
    expect(of("social_error=social_state_invalid")).toEqual({ kind: "refused", problem: "social_state_invalid" });
    expect(of("social_error=social_failed")).toEqual({ kind: "refused", problem: "unknown" });
  });

  it("ignores a consent ticket of an unknown provider", () => {
    expect(of("social_consent=t-3&social_provider=myspace")).toEqual({ kind: "none" });
    expect(of("")).toEqual({ kind: "none" });
  });
});

it("keeps the page to return to in the refusal address", () => {
  expect(socialRefusalPath("/app/login", "unknown", "/app/kanban")).toBe(
    "/app/login?social_error=unknown&next=%2Fapp%2Fkanban",
  );
});
