import { describe, expect, it } from "vitest";

import { askLeo, listenForQuestions } from "./leo-questions";

describe("questions for Leo from elsewhere in the cabinet", () => {
  it("reach the widget on the page, trimmed", () => {
    const heard: string[] = [];
    const stop = listenForQuestions((question) => heard.push(question));

    expect(askLeo("  what did we agree with Lumen?  ")).toBe(true);
    stop();

    expect(heard).toEqual(["what did we agree with Lumen?"]);
  });

  it("go nowhere without a widget, and blank ones never go", () => {
    const heard: string[] = [];
    const stop = listenForQuestions((question) => heard.push(question));

    expect(askLeo("   ")).toBe(false);
    stop();
    expect(askLeo("hello")).toBe(false);
    expect(heard).toEqual([]);
  });
});
