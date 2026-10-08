import { describe, it } from "vitest";

import { layoutMindMap, NODE_WIDTH } from "./mind-map-layout";
import assert from "node:assert/strict";

describe("layoutMindMap", () => {
  const root = { label: "Root", children: [{ label: "A" }, { label: "B" }] };
  it("grows to the right left to right, and to the left right to left", () => {
    const ltr = layoutMindMap(root);
    const rtl = layoutMindMap(root, true);
    const rootOf = (nodes: { id: string; x: number }[]) => nodes.find((node) => node.id === "root")?.x;
    assert.equal(rootOf(ltr.nodes), 0);
    assert.equal(rootOf(rtl.nodes), ltr.width - NODE_WIDTH);
    for (const node of rtl.nodes) {
      const mirror = ltr.nodes.find((other) => other.id === node.id);
      assert.equal(node.x, ltr.width - NODE_WIDTH - (mirror?.x ?? Number.NaN));
    }
    // Edges leave the root from its left side and reach each child's right side.
    assert.match(rtl.edges[0].path, new RegExp(`^M${rtl.width - NODE_WIDTH} `));
  });
});
