import { describe, expect, it } from "vitest";

import { blocksOf, lexed, type MdBlock, type MdInline } from "./markdown";

const blocks = (text: string) => blocksOf(lexed(text));
const inlines = (text: string): MdInline[] => {
  const first = blocks(text)[0];
  return first?.type === "paragraph" ? first.children : [];
};
const maths = (text: string) => inlines(text).filter((node) => node.type === "math");

describe("formulas in Leo's Markdown", () => {
  it("reads inline formulas between $…$, \\(…\\) and $$…$$", () => {
    expect(maths("grows as $U(t) = U_0 e^{kt}$, so")).toMatchObject([{ tex: "U(t) = U_0 e^{kt}", display: false }]);
    expect(maths("converts at \\(\\frac{18}{120} = 15\\%\\).")).toMatchObject([
      { tex: "\\frac{18}{120} = 15\\%", display: false },
    ]);
    expect(maths("so $$a = b$$ holds")).toMatchObject([{ tex: "a = b", display: true }]);
  });

  it("leaves prices, escaped dollars and code alone", () => {
    expect(maths("A price of $15 a seat stays a price.")).toEqual([]);
    expect(maths("from $5 to $10 a month")).toEqual([]);
    expect(maths("between $5-$10")).toEqual([]);
    expect(maths("costs \\$5 and \\$6")).toEqual([]);
    expect(inlines("run `echo $HOME $PATH` first")).toMatchObject([
      { type: "text" },
      { type: "code", text: "echo $HOME $PATH" },
      { type: "text" },
    ]);
  });

  it("keeps underscores and stars inside a formula out of emphasis", () => {
    expect(maths("the sum $a_1 + a_2 * b_2$ here")).toMatchObject([{ tex: "a_1 + a_2 * b_2" }]);
  });

  it("draws block formulas from $$, \\[ and math fences only once they are closed", () => {
    expect(blocks("$$\nU(30) = 120 \\cdot e^{1.5}\n$$\n\nafter")[0]).toEqual<MdBlock>({
      key: "0",
      type: "math",
      tex: "U(30) = 120 \\cdot e^{1.5}",
    });
    expect(blocks("\\[x^2 + y^2\\]")[0]).toMatchObject({ type: "math", tex: "x^2 + y^2" });
    expect(blocks("```latex\n\\int_0^1 x\\,dx\n```")[0]).toMatchObject({ type: "math", tex: "\\int_0^1 x\\,dx" });
    expect(blocks("$$\nU(30) = 120")[0].type).toBe("paragraph");
    expect(blocks("```math\nx^2")[0]).toMatchObject({ type: "code", lang: "math", closed: false });
  });
});
