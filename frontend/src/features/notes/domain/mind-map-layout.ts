import type { MindMapNode } from "./types";

export const NODE_WIDTH = 152;
export const NODE_HEIGHT = 36;
const COLUMN_GAP = 56;
const ROW_GAP = 14;

export interface PositionedNode {
  id: string;
  label: string;
  depth: number;
  x: number;
  y: number;
}

export interface MindMapEdge {
  id: string;
  /** An SVG path from the parent's side facing the child to the child's side facing the parent. */
  path: string;
}

/**
 * Lays the map out as a tree that grows along the line of text: one column per depth, leaves stacked evenly,
 * and every parent centred on its children. Left to right by default; `rtl` mirrors it, so the root sits at
 * the right and branches grow towards the end of a right-to-left line.
 */
export function layoutMindMap(root: MindMapNode, rtl = false) {
  const placed: PositionedNode[] = [];
  const links: { id: string; from: PositionedNode; to: PositionedNode }[] = [];
  let nextLeafRow = 0;

  function place(node: MindMapNode, depth: number, id: string): PositionedNode {
    const x = depth * (NODE_WIDTH + COLUMN_GAP);
    const children = (node.children ?? []).map((child, index) => place(child, depth + 1, `${id}-${index}`));

    let y: number;
    if (children.length === 0) {
      y = nextLeafRow * (NODE_HEIGHT + ROW_GAP);
      nextLeafRow += 1;
    } else {
      y = (children[0].y + children[children.length - 1].y) / 2;
    }

    const positioned = { id, label: node.label, depth, x, y };
    placed.push(positioned);
    for (const child of children) links.push({ id: `${id}->${child.id}`, from: positioned, to: child });
    return positioned;
  }

  place(root, 0, "root");

  const width = Math.max(...placed.map((n) => n.x)) + NODE_WIDTH;
  const height = Math.max(...placed.map((n) => n.y)) + NODE_HEIGHT;
  // Mirroring swaps which side of a node faces its children: the start of a line is on the right.
  const left = (node: PositionedNode) => (rtl ? width - NODE_WIDTH - node.x : node.x);
  const nodes = placed.map((node) => ({ ...node, x: left(node) }));
  const edges: MindMapEdge[] = links.map(({ id, from, to }) => {
    const startX = rtl ? left(from) : left(from) + NODE_WIDTH;
    const endX = rtl ? left(to) + NODE_WIDTH : left(to);
    const startY = from.y + NODE_HEIGHT / 2;
    const endY = to.y + NODE_HEIGHT / 2;
    const midX = (startX + endX) / 2;
    return { id, path: `M${startX} ${startY}C${midX} ${startY} ${midX} ${endY} ${endX} ${endY}` };
  });
  return { nodes, edges, width, height };
}
