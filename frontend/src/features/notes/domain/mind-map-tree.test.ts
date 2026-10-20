import { describe, it } from "vitest";

import { mindMapTree } from "./mind-map-tree";
import assert from "node:assert/strict";

describe("mindMapTree", () => {
  it("builds the tree from nodes in preorder, keeping the server's order of children", () => {
    const tree = mindMapTree([
      { id: "r", parentId: null, label: "Launch" },
      { id: "a", parentId: "r", label: "Pricing" },
      { id: "a1", parentId: "a", label: "Pro" },
      { id: "b", parentId: "r", label: "Dates" },
    ]);

    assert.deepEqual(tree, {
      label: "Launch",
      children: [
        { label: "Pricing", children: [{ label: "Pro", children: [] }] },
        { label: "Dates", children: [] },
      ],
    });
  });

  it("answers null for a map without nodes", () => {
    assert.equal(mindMapTree([]), null);
  });

  it("keeps the first root and drops a node whose parent never came", () => {
    const tree = mindMapTree([
      { id: "r", parentId: null, label: "Launch" },
      { id: "x", parentId: "missing", label: "Stray" },
    ]);

    assert.deepEqual(tree, { label: "Launch", children: [] });
  });
});
