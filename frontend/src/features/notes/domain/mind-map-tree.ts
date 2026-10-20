import type { MindMapNode } from "./types";

/** Узел карты, как его отдаёт сервер: в прямом порядке обхода, с id родителя. */
export interface FlatMapNode {
  id: string;
  parentId: string | null;
  label: string;
}

/** Дерево карты из узлов в прямом порядке; null, если корня нет. */
export function mindMapTree(nodes: readonly FlatMapNode[]): MindMapNode | null {
  const built = new Map<string, MindMapNode>();
  let root: MindMapNode | null = null;
  for (const node of nodes) {
    const tree: MindMapNode = { label: node.label, children: [] };
    built.set(node.id, tree);
    const parent = node.parentId === null ? undefined : built.get(node.parentId);
    if (parent) parent.children?.push(tree);
    else root ??= tree;
  }
  return root;
}
