"use client";

import { type FormEvent, useEffect, useRef, useState } from "react";

import type { Editor } from "@tiptap/core";
import { useEditorState } from "@tiptap/react";
import { Bold, Italic, Link2 } from "lucide-react";
import { useTranslations } from "use-intl";

import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from "@/components/ui/input-group";
import { Separator } from "@/components/ui/separator";
import { Toggle } from "@/components/ui/toggle";

import { EditorBlockMenu } from "./editor-block-menu";
import { currentBlock } from "./editor-blocks";

/** A typed address with no scheme gets https, so "acme.com" links to the site rather than a relative path. */
const withScheme = (url: string) => (/^[a-z][a-z\d+.-]*:/i.test(url) ? url : `https://${url}`);

/** The floating toolbar over a selection: link, bold, italic and the block's kind. */
export function EditorToolbar({ editor }: { editor: Editor }) {
  const t = useTranslations("notesNote");
  const [linking, setLinking] = useState(false);
  const state = useEditorState({
    editor,
    selector: ({ editor: current }) => ({
      bold: current.isActive("bold"),
      italic: current.isActive("italic"),
      link: current.isActive("link"),
      block: currentBlock(current),
    }),
  });

  if (linking) return <LinkField editor={editor} onDone={() => setLinking(false)} />;

  return (
    <div
      role="toolbar"
      aria-label={t("editor.toolbar")}
      className="flex items-center gap-0.5 rounded-lg bg-popover p-1 text-popover-foreground shadow-md ring-1 ring-foreground/10"
    >
      <Toggle
        size="sm"
        aria-label={state.link ? t("editor.removeLink") : t("editor.addLink")}
        pressed={state.link}
        onPressedChange={() => (state.link ? editor.chain().focus().unsetLink().run() : setLinking(true))}
      >
        <Link2 />
      </Toggle>
      <Toggle
        size="sm"
        aria-label={t("editor.bold")}
        pressed={state.bold}
        onPressedChange={() => editor.chain().focus().toggleBold().run()}
      >
        <Bold />
      </Toggle>
      <Toggle
        size="sm"
        aria-label={t("editor.italic")}
        pressed={state.italic}
        onPressedChange={() => editor.chain().focus().toggleItalic().run()}
      >
        <Italic />
      </Toggle>
      <Separator orientation="vertical" className="mx-0.5 h-5" />
      <EditorBlockMenu editor={editor} current={state.block} />
    </div>
  );
}

function LinkField({ editor, onDone }: { editor: Editor; onDone: () => void }) {
  const t = useTranslations("notesNote");
  const inputRef = useRef<HTMLInputElement>(null);
  // Opened from the link button, which it replaces, so it takes the focus.
  useEffect(() => inputRef.current?.focus(), []);

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const url = String(new FormData(event.currentTarget).get("url") ?? "").trim();
    if (url)
      editor
        .chain()
        .focus()
        .extendMarkRange("link")
        .setLink({ href: withScheme(url) })
        .run();
    else editor.chain().focus().run();
    onDone();
  };

  return (
    <form onSubmit={submit} noValidate className="w-72 rounded-lg bg-popover p-1 shadow-md ring-1 ring-foreground/10">
      <InputGroup>
        <InputGroupInput
          ref={inputRef}
          name="url"
          inputMode="url"
          dir="auto"
          placeholder={t("editor.linkPlaceholder")}
          aria-label={t("editor.linkAddress")}
          autoComplete="off"
          spellCheck={false}
          onKeyDown={(event) => {
            if (event.key !== "Escape") return;
            event.preventDefault();
            editor.chain().focus().run();
            onDone();
          }}
        />
        <InputGroupAddon align="inline-end">
          <InputGroupButton type="submit">{t("editor.link")}</InputGroupButton>
        </InputGroupAddon>
      </InputGroup>
    </form>
  );
}
