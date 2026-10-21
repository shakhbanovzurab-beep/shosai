"use client";

import { type KeyboardEvent, useRef, useState } from "react";

import type { Editor } from "@tiptap/core";
import { cn } from "cn";
import { Check, ChevronDown } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";

import { applyBlock, BLOCKS, type BlockKind } from "./editor-blocks";

// Shown as the shortcut hint; macOS draws the keys, elsewhere they're spelled out.
const isMac = () => typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.userAgent);

/**
 * "Text ▾": the kind of the block at the cursor, and the menu to change it. It opens inside the toolbar
 * rather than in a portal, so the editor keeps its selection and the floating toolbar stays up.
 */
export function EditorBlockMenu({ editor, current }: { editor: Editor; current: BlockKind }) {
  const t = useTranslations("common");
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const shortcut = isMac() ? "⌥⌘" : "Ctrl+Alt+";

  const items = () => [...(listRef.current?.querySelectorAll<HTMLButtonElement>("[role=menuitemradio]") ?? [])];
  const close = () => {
    setOpen(false);
    triggerRef.current?.focus();
  };
  const choose = (kind: BlockKind) => {
    setOpen(false);
    applyBlock(editor, kind, current);
  };
  const moveFocus = (event: KeyboardEvent) => {
    const all = items();
    const at = all.indexOf(document.activeElement as HTMLButtonElement);
    if (event.key === "Escape") close();
    else if (event.key === "ArrowDown") all[(at + 1) % all.length]?.focus();
    else if (event.key === "ArrowUp") all[(at - 1 + all.length) % all.length]?.focus();
    else return;
    event.preventDefault();
  };

  return (
    <div className="relative">
      <Button
        ref={triggerRef}
        variant="ghost"
        size="sm"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        onKeyDown={(event) => {
          if (event.key !== "ArrowDown") return;
          event.preventDefault();
          setOpen(true);
          requestAnimationFrame(() => items()[0]?.focus());
        }}
      >
        {t(`editor.blocks.${current}`)}
        <ChevronDown data-icon="inline-end" />
      </Button>
      {open ? (
        <div
          ref={listRef}
          role="menu"
          aria-label={t("editor.turnInto")}
          onKeyDown={moveFocus}
          className="absolute start-0 bottom-full mb-2 flex w-60 flex-col rounded-lg bg-popover p-1 text-popover-foreground shadow-md ring-1 ring-foreground/10"
        >
          {BLOCKS.map((block) => (
            <button
              key={block.kind}
              type="button"
              role="menuitemradio"
              aria-checked={block.kind === current}
              onClick={() => choose(block.kind)}
              className={cn(
                "flex items-center gap-2 rounded-md px-2 py-1.5 text-start text-sm outline-none hover:bg-accent focus-visible:bg-accent",
                block.kind === current && "bg-accent",
                block.className,
              )}
            >
              <span className="flex-1">{t(`editor.blocks.${block.kind}`)}</span>
              {block.kind === current ? <Check className="size-3.5 text-muted-foreground" aria-hidden="true" /> : null}
              {/* Keys read left to right, as printed on the keyboard. */}
              <kbd dir="ltr" className="font-normal font-sans text-muted-foreground text-xs tracking-widest">
                {shortcut}
                {block.key}
              </kbd>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
