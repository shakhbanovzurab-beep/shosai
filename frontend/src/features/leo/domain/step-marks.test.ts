import { describe, expect, it } from "vitest";

import { stepMark } from "./step-marks";

describe("stepMark", () => {
  it("marks the web's steps with the globe, by flat code or by tool", () => {
    expect(stepMark("web_search")).toBe("web");
    expect(stepMark("web_read")).toBe("web");
    expect(stepMark("web.search")).toBe("web");
    expect(stepMark("web")).toBe("web");
  });

  it("marks a search in the person's data with the magnifier", () => {
    expect(stepMark("search_knowledge")).toBe("search");
    expect(stepMark("notes.search")).toBe("search");
    expect(stepMark("files.search")).toBe("search");
  });

  it("gives every other step a dot, words that only contain “search” included", () => {
    expect(stepMark("think")).toBe("dot");
    expect(stepMark("notes.read_transcript")).toBe("dot");
    expect(stepMark("research_plan")).toBe("dot");
    expect(stepMark("website_audit")).toBe("dot");
  });
});
