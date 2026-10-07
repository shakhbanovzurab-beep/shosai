import type { Editor } from "@tiptap/core";

export type BlockKind = "text" | "h1" | "h2" | "h3" | "ordered" | "bullet";

/** The kinds of block, with the digit of each one's shortcut; the `notesNote` catalog names them. */
export const BLOCKS: { kind: BlockKind; key: string; className?: string }[] = [
  { kind: "text", key: "0" },
  { kind: "h1", key: "1", className: "font-semibold text-base" },
  { kind: "h2", key: "2", className: "font-semibold" },
  { kind: "h3", key: "3", className: "font-medium" },
  { kind: "ordered", key: "4" },
  { kind: "bullet", key: "5" },
];

const HEADING_LEVELS = { h1: 1, h2: 2, h3: 3 } as const;

export function currentBlock(editor: Editor): BlockKind {
  if (editor.isActive("orderedList")) return "ordered";
  if (editor.isActive("bulletList")) return "bullet";
  if (editor.isActive("heading", { level: 1 })) return "h1";
  if (editor.isActive("heading", { level: 2 })) return "h2";
  if (editor.isActive("heading", { level: 3 })) return "h3";
  return "text";
}

/** Turns the block at the cursor into another kind; a list item leaves its list to become text or a heading. */
export function applyBlock(editor: Editor, kind: BlockKind, current: BlockKind) {
  if (kind === current) return;
  const chain = editor.chain().focus();
  if (kind === "ordered" || kind === "bullet") {
    if (current in HEADING_LEVELS) chain.setParagraph();
    if (kind === "ordered") chain.toggleOrderedList();
    else chain.toggleBulletList();
  } else {
    if (current === "ordered") chain.toggleOrderedList();
    if (current === "bullet") chain.toggleBulletList();
    if (kind === "text") chain.setParagraph();
    else chain.setHeading({ level: HEADING_LEVELS[kind] });
  }
  chain.run();
}
