import { describe, expect, it } from "vitest";

import { blocksOf, decoded, lexed, safeHref } from "./markdown";
import { citedParts, citesIn } from "./markdown-cites";
import { parsed } from "./markdown-stream";

const blocks = (text: string) => blocksOf(lexed(text));
const flat = (value: unknown) => JSON.stringify(value);

describe("Leo's Markdown", () => {
  it("keeps raw HTML as text and never links or loads what is not allowed", () => {
    const out = flat(
      blocks(
        "<script>alert(1)</script>\n\n<img src=x onerror=alert(1)> [a](javascript:alert(1)) ![p](https://x/t.png) [b](//evil.example) [c](data:text/html,x)",
      ),
    );

    expect(out).toContain('"text":"<script>alert(1)</script>"');
    expect(out).not.toContain('"type":"link"');
    expect(out).not.toContain("t.png");
    expect(out).toContain('"text":"p"');
  });

  it("links the web, mail and the cabinet's own pages", () => {
    expect(safeHref("https://shosai.tech")).toBe("https://shosai.tech");
    expect(safeHref(" mailto:a@b.c")).toBe("mailto:a@b.c");
    expect(safeHref("/app/notes/1")).toBe("/app/notes/1");
    expect(["javascript:x", "JavaScript:x", "//x.y", "/\\x.y", "vbscript:x", "file:///etc"].map(safeHref)).toEqual([
      null,
      null,
      null,
      null,
      null,
      null,
    ]);
  });

  it("reads unfinished Markdown as text while it is being written", () => {
    expect(flat(blocks("Some **bold"))).toContain("**bold");
    expect(blocks("```ts\nconst a = 1")[0]).toEqual({ key: "0", type: "code", lang: "ts", text: "const a = 1" });
    expect(blocks("| a | b |\n|--")[0].type).toBe("paragraph");
    expect(blocks("1. one\n2.")[0].type).toBe("list");
  });

  it("builds lists, tables, quotes and headings", () => {
    expect(blocks("# Plan").at(0)).toEqual({
      key: "0",
      type: "heading",
      depth: 1,
      children: [{ key: "0", type: "text", text: "Plan" }],
    });
    expect(blocks("| a | b |\n|:-|-:|\n| 1 | 2 |")[0]).toMatchObject({ type: "table", align: ["left", "right"] });
    expect(blocks("> said")[0].type).toBe("quote");
    expect(blocks("3. c\n4. d")[0]).toMatchObject({ type: "list", ordered: true, start: 3 });
  });

  it("decodes entities the model wrote, React escapes the rest", () => {
    expect(decoded("a &amp; b &lt;i&gt; &#x41; &#66; &bogus;")).toBe("a & b <i> A B &bogus;");
  });

  it("parses a growing answer block by block, reusing the finished ones", () => {
    const answer = "# Budget\n\nTravel is cut [1].\n\n- one\n- two\n\nNext steps are open.";
    let doc = parsed("", null);
    const seen = new Map<number, object>();
    for (let end = 1; end <= answer.length; end += 3) {
      doc = parsed(answer.slice(0, end), doc);
      doc.parts.slice(0, -1).forEach((part, index) => {
        const before = seen.get(index);
        if (before !== undefined) expect(part).toBe(before);
        seen.set(index, part);
      });
    }
    doc = parsed(answer, doc);

    expect(flat(doc.parts)).toBe(flat(parsed(answer, null).parts));
    expect(parsed("Other text", doc).text).toBe("Other text");
  });
});

describe("the sources an answer cites", () => {
  it("draws only the numbers the run's sources have", () => {
    expect(citedParts("Cut [1], kept [2][9] and [x].", 2)).toEqual([
      { key: 0, text: "Cut " },
      { key: 4, n: 1, tail: "," },
      { key: 8, text: " kept " },
      { key: 14, n: 2, tail: "" },
      { key: 17, text: "[9] and [x]." },
    ]);
  });

  it("keeps the stop after a number on the number's line", () => {
    expect(citedParts("It holds [1]. Then [2]]", 2)).toEqual([
      { key: 0, text: "It holds " },
      { key: 9, n: 1, tail: "." },
      { key: 13, text: " Then " },
      { key: 19, n: 2, tail: "]" },
    ]);
  });

  it("finds the numbers a block rests on, inside lists and tables too", () => {
    expect([...citesIn(blocks("- travel [2]\n- food [1]\n\n| a |\n|---|\n| b [3] |"), 3)].toSorted()).toEqual([
      1, 2, 3,
    ]);
  });
});
