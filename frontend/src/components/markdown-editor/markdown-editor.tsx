"use client";

import { useEffect } from "react";

import { Extension } from "@tiptap/core";
import { Placeholder } from "@tiptap/extensions";
import { Markdown } from "@tiptap/markdown";
import { EditorContent, useEditor } from "@tiptap/react";
import { BubbleMenu } from "@tiptap/react/menus";
import { StarterKit } from "@tiptap/starter-kit";

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
  "break-words text-sm leading-relaxed outline-none",
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

const editorAttributes = (label: string, size: string) => ({
  class: `${DOCUMENT_CLASS} ${size}`,
  "aria-label": label,
  role: "textbox",
  "aria-multiline": "true",
});

interface MarkdownEditorProps {
  /** Текст в Markdown при открытии; дальше текстом владеет редактор. */
  readonly initialMarkdown: string;
  readonly onChange: (markdown: string) => void;
  /** Уход из редактора или ⌘S: сохранить сейчас, а не после паузы. */
  readonly onFlush: () => void;
  /** Подпись поля для чтения с экрана и подсказка в пустом документе — словами того, кто показывает редактор. */
  readonly label: string;
  readonly placeholder: string;
  /** Высота пустого документа, классом Tailwind (`min-h-48`). */
  readonly minHeight: string;
}

/**
 * Документ в Markdown для правки: выделите текст — появится панель форматирования. Каждый абзац берёт
 * направление своего текста, поэтому текст на любом письме читается верно; слова самого редактора — на языке
 * интерфейса. Им пишут свои заметки в Notes и описание задачи в Канбане.
 */
export function MarkdownEditor({
  initialMarkdown,
  onChange,
  onFlush,
  label,
  placeholder,
  minHeight,
}: MarkdownEditorProps) {
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
      Placeholder.configure({ placeholder }),
      Markdown,
      ListShortcuts,
    ],
    content: initialMarkdown,
    contentType: "markdown",
    editorProps: {
      attributes: editorAttributes(label, minHeight),
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

  // Редактор создаётся один раз; после смены языка ему передаются новые подсказка и подпись.
  useEffect(() => {
    if (!editor || editor.isDestroyed) return;
    const extension = editor.extensionManager.extensions.find((item) => item.name === "placeholder");
    if (extension) extension.options.placeholder = placeholder;
    editor.setOptions({
      editorProps: { ...editor.options.editorProps, attributes: editorAttributes(label, minHeight) },
    });
    // Пустая транзакция перерисовывает подсказку, не трогая текст.
    editor.view.dispatch(editor.state.tr);
  }, [editor, label, placeholder, minHeight]);

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
