import { describe, it } from "vitest";

import { ApiError } from "@/lib/api/errors";

import { isApiCode, noteProblemOf, runFailureOf } from "./problems";
import assert from "node:assert/strict";

const refused = (code: string | null) => new ApiError(code ?? "HTTP 500", 409, code);

describe("noteProblemOf", () => {
  it("knows the notes slice's codes", () => {
    assert.equal(noteProblemOf(refused("meeting_read_only")), "meeting_read_only");
    assert.equal(noteProblemOf(refused("meetings_not_kept")), "meetings_not_kept");
  });

  it("leaves any other failure to the server's text", () => {
    assert.equal(noteProblemOf(refused("quota_exceeded")), null);
    assert.equal(noteProblemOf(refused(null)), null);
    assert.equal(noteProblemOf(new Error("meeting_read_only")), null);
  });
});

describe("runFailureOf", () => {
  it("names the stages that won't succeed on a retry, and the rest as one failure", () => {
    assert.equal(runFailureOf("consent_required"), "consent_required");
    assert.equal(runFailureOf("provider_timeout"), "other");
    assert.equal(runFailureOf(null), "other");
  });
});

describe("isApiCode", () => {
  it("tells a known code from any other failure", () => {
    assert.equal(isApiCode(refused("write_up_not_found"), "write_up_not_found"), true);
    assert.equal(isApiCode(refused("meeting_not_found"), "write_up_not_found"), false);
    assert.equal(isApiCode(new Error("write_up_not_found"), "write_up_not_found"), false);
  });
});
