"use client";

import { useEffect } from "react";

import { Extension } from "@tiptap/core";
import { Placeholder } from "@tiptap/extensions";
import { Markdown } from "@tiptap/markdown";
import { EditorContent, useEditor } from "@tiptap/react";
import { BubbleMenu } from "@tiptap/react/menus";
import { StarterKit } from "@tiptap/starter-kit";
import { useTranslations } from "use-intl";

import { EditorToolbar } from "./editor-toolbar";

/** ⌥⌘4 and ⌥⌘5 for lists, next to the built-in ⌥⌘0 (text) and ⌥⌘1–3 (headings). */
const ListShortcuts = Extension.create({
  name: "listShortcuts",
  addKeyboardShortcuts() {
    return {
      "Mod-Alt-4": () => this.editor.commands.toggleOrderedList(),
      "Mod-Alt-5": () => this.editor.commands.toggleBulletList(),
    };
  },
});

// Styles for the editable document; the theme has no typography plugin, so each element is styled here.
const DOCUMENT_CLASS = [
  "min-h-48 break-words text-sm leading-relaxed outline-none",
  "[&>*+*]:mt-3 [&_li+li]:mt-1 [&_li>p]:m-0",
  "[&_h1]:pt-2 [&_h1]:font-semibold [&_h1]:text-xl [&_h2]:pt-1 [&_h2]:font-semibold [&_h2]:text-lg",
  "[&_h3]:font-semibold [&_h3]:text-base [&>:first-child]:pt-0",
  "[&_ol]:list-decimal [&_ol]:ps-5 [&_ul]:list-disc [&_ul]:ps-5 [&_ul_ul]:list-[circle] [&_li]:marker:text-muted-foreground",
  "[&_ol_ol]:mt-1 [&_ul_ul]:mt-1 [&_a]:underline [&_a]:underline-offset-4",
  // The placeholder Tiptap puts on the first empty paragraph.
  "[&_.is-editor-empty:first-child]:before:pointer-events-none [&_.is-editor-empty:first-child]:before:float-start",
  "[&_.is-editor-empty:first-child]:before:h-0 [&_.is-editor-empty:first-child]:before:text-muted-foreground",
  "[&_.is-editor-empty:first-child]:before:content-[attr(data-placeholder)]",
].join(" ");

const editorAttributes = (label: string) => ({
  class: DOCUMENT_CLASS,
  "aria-label": label,
  role: "textbox",
  "aria-multiline": "true",
});

interface NotesEditorProps {
  /** The notes as Markdown when the editor opens; after that the editor owns the text. */
  readonly initialMarkdown: string;
  readonly onChange: (markdown: string) => void;
  /** Leaving the editor, or ⌘S: save now instead of after the pause. */
  readonly onFlush: () => void;
}

/**
 * The user's own notes as an editable document: select text for the formatting toolbar. Each paragraph takes
 * the direction of its own text, so notes in any script read right; the editor's own words follow the interface.
 */
export function NotesEditor({ initialMarkdown, onChange, onFlush }: NotesEditorProps) {
  const t = useTranslations("notesNote");
  const editor = useEditor({
    immediatelyRender: false,
    textDirection: "auto",
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
        blockquote: false,
        code: false,
        codeBlock: false,
        horizontalRule: false,
        strike: false,
        underline: false,
        link: { openOnClick: false, autolink: true, defaultProtocol: "https" },
      }),
      Placeholder.configure({ placeholder: t("editor.placeholder") }),
      Markdown,
      ListShortcuts,
    ],
    content: initialMarkdown,
    contentType: "markdown",
    editorProps: {
      attributes: editorAttributes(t("editor.label")),
      handleKeyDown: (_view, event) => {
        if (!((event.metaKey || event.ctrlKey) && event.key === "s")) return false;
        event.preventDefault();
        onFlush();
        return true;
      },
    },
    // The empty paragraph the editor keeps at the end would otherwise save as trailing blank lines.
    onUpdate: ({ editor: current }) => onChange(current.getMarkdown().trimEnd()),
    onBlur: () => onFlush(),
  });

  // The editor is made once; after a language switch, hand it the new placeholder and label.
  useEffect(() => {
    if (!editor || editor.isDestroyed) return;
    const placeholder = editor.extensionManager.extensions.find((extension) => extension.name === "placeholder");
    if (placeholder) placeholder.options.placeholder = t("editor.placeholder");
    editor.setOptions({
      editorProps: { ...editor.options.editorProps, attributes: editorAttributes(t("editor.label")) },
    });
    // An empty transaction redraws the placeholder without touching the text.
    editor.view.dispatch(editor.state.tr);
  }, [editor, t]);

  return (
    <>
      {editor ? (
        <BubbleMenu editor={editor} options={{ placement: "top-start", offset: 8 }}>
          <EditorToolbar editor={editor} />
        </BubbleMenu>
      ) : null}
      <EditorContent editor={editor} />
    </>
  );
}
