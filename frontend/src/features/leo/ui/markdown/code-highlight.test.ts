import { createElement } from "react";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { highlightedCode } from "./code-highlight";

const markup = (lang: string, code: string) =>
  renderToStaticMarkup(createElement("code", null, highlightedCode(lang, code)));

describe("highlightedCode", () => {
  it("colours a known language by its fence name or alias", () => {
    const html = markup("ts", "const total: number = 1; // sum");
    expect(html).toContain('<span class="text-rose-700 dark:text-rose-400">const</span>');
    expect(html).toContain('<span class="text-blue-700 dark:text-blue-300">1</span>');
    expect(html).toContain('<span class="text-muted-foreground italic">// sum</span>');
    expect(markup("python", "def churn(): pass")).toContain("text-rose-700");
  });

  it("leaves an unknown or missing language to plain text", () => {
    expect(highlightedCode("", "x = 1")).toBeNull();
    expect(highlightedCode("not-a-language", "x = 1")).toBeNull();
  });

  it("keeps markup inside the code as text, never as HTML", () => {
    const html = markup("html", '<img src=x onerror="alert(1)"><script>alert(2)</script>');
    expect(html).not.toContain("<img");
    expect(html).not.toContain("<script");
    expect(html).toContain("&lt;");
    expect(html).toContain("alert(2)");
  });
});
