import katex from "katex";
import { describe, expect, it } from "vitest";

import { MATH_OPTIONS } from "./math-render";

const html = (tex: string) => katex.renderToString(tex, MATH_OPTIONS);

describe("KaTeX options for Leo's formulas", () => {
  it("draws a formula, with MathML for screen readers", () => {
    expect(html("\\frac{1}{2}")).toContain("<math");
  });

  it("trusts no command that links out or writes its own markup", () => {
    for (const tex of [
      "\\href{javascript:alert(1)}{x}",
      "\\url{javascript:alert(1)}",
      "\\htmlClass{evil}{x}",
      "\\htmlData{onload=alert(1)}{x}",
      "\\includegraphics{https://evil.example/t.png}",
    ]) {
      const out = html(tex);
      expect(out).not.toMatch(/<a[\s>]/);
      expect(out).not.toMatch(/<img[\s>]/);
      expect(out).not.toMatch(/href=/);
      expect(out).not.toContain('class="evil"');
      expect(out).not.toContain("data-onload");
    }
  });

  it("caps sizes and macro expansion, and never throws on bad input", () => {
    expect(() => html("\\def\\a{\\a\\a}\\a")).not.toThrow();
    expect(() => html("\\frac{")).not.toThrow();
    // Исходник остаётся в аннотации MathML, а нарисованный размер — не больше 20em.
    expect(html("\\rule{1000em}{1000em}")).toContain("border-right-width:20em");
  });
});
