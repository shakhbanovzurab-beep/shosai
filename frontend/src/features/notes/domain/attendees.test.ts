import { describe, it } from "vitest";

import { attendeeProblem, isOwnEmail } from "./attendees";
import assert from "node:assert/strict";

const attendees = [{ email: "Anna@Company.com" }, { email: null }];

describe("attendeeProblem", () => {
  it("asks for an email address", () => {
    assert.equal(attendeeProblem("anna", attendees), "invalid");
    assert.equal(attendeeProblem("  ", attendees), "invalid");
  });

  it("finds a person already in the meeting, whatever the case and spaces", () => {
    assert.equal(attendeeProblem(" anna@company.com ", attendees), "duplicate");
  });

  it("lets a new address in; a person known only by voice has no address to clash with", () => {
    assert.equal(attendeeProblem("ivan@company.com", attendees), null);
  });
});

describe("isOwnEmail", () => {
  it("compares addresses without case", () => {
    assert.equal(isOwnEmail("ANNA@company.com", "anna@company.com"), true);
    assert.equal(isOwnEmail("ivan@company.com", "anna@company.com"), false);
  });
});
