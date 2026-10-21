import { describe, expect, it } from "vitest";

import { linkParts } from "./link-parts";

describe("links in a comment", () => {
  it("keeps plain text as one part", () => {
    expect(linkParts("No links here.")).toEqual([{ text: "No links here.", href: null, start: 0 }]);
  });

  it("makes each link its own part and leaves trailing punctuation outside", () => {
    expect(linkParts("See https://orm.drizzle.team, and http://a.example/x?y=1.")).toEqual([
      { text: "See ", href: null, start: 0 },
      { text: "https://orm.drizzle.team", href: "https://orm.drizzle.team", start: 4 },
      { text: ", and ", href: null, start: 28 },
      { text: "http://a.example/x?y=1", href: "http://a.example/x?y=1", start: 34 },
      { text: ".", href: null, start: 56 },
    ]);
  });

  it("takes only web links, not other schemes", () => {
    expect(linkParts("javascript:alert(1) ftp://x")).toEqual([
      { text: "javascript:alert(1) ftp://x", href: null, start: 0 },
    ]);
  });

  it("keeps the whole text, link at the start or the end", () => {
    const text = "https://a.example (see) https://b.example";
    expect(
      linkParts(text)
        .map((part) => part.text)
        .join(""),
    ).toBe(text);
  });
});
