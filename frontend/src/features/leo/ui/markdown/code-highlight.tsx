import type { ReactNode } from "react";

import type { ElementContent, RootContent } from "hast";
import { common, createLowlight } from "lowlight";

/*
 * Подсветка кода в ответе Leo: грамматики highlight.js через lowlight дают дерево hast, кабинет рисует его своими
 * элементами — ни строки HTML модели в разметку не попадает. Модуль грузится лениво, с первым блоком кода.
 */

const lowlight = createLowlight(common);

// Цвета токенов: на фоне блока каждый держит контраст текста 4.5:1 в светлой и тёмной теме.
const STRING = "text-sky-800 dark:text-sky-300";
const NUMBER = "text-blue-700 dark:text-blue-300";
const TOKEN_CLASSES: Record<string, string> = {
  "hljs-keyword": "text-rose-700 dark:text-rose-400",
  "hljs-literal": "text-rose-700 dark:text-rose-400",
  "hljs-doctag": "text-rose-700 dark:text-rose-400",
  "hljs-selector-tag": "text-rose-700 dark:text-rose-400",
  "hljs-string": STRING,
  "hljs-regexp": STRING,
  "hljs-char": STRING,
  "hljs-number": NUMBER,
  "hljs-symbol": NUMBER,
  "hljs-attr": NUMBER,
  "hljs-attribute": NUMBER,
  "hljs-property": NUMBER,
  "hljs-selector-attr": NUMBER,
  "hljs-selector-class": NUMBER,
  "hljs-selector-id": NUMBER,
  "hljs-title": "text-violet-700 dark:text-violet-300",
  "hljs-section": "text-violet-700 dark:text-violet-300 font-semibold",
  "hljs-type": "text-amber-700 dark:text-amber-300",
  "hljs-built_in": "text-amber-700 dark:text-amber-300",
  "hljs-variable": "text-orange-700 dark:text-orange-300",
  "hljs-template-variable": "text-orange-700 dark:text-orange-300",
  "hljs-params": "text-foreground",
  "hljs-name": "text-green-700 dark:text-green-300",
  "hljs-tag": "text-muted-foreground",
  "hljs-meta": "text-muted-foreground",
  "hljs-comment": "text-muted-foreground italic",
  "hljs-quote": "text-muted-foreground italic",
  "hljs-addition": "text-green-700 dark:text-green-300 bg-green-500/10",
  "hljs-deletion": "text-red-700 dark:text-red-300 bg-red-500/10",
  "hljs-emphasis": "italic",
  "hljs-strong": "font-semibold",
};

function classesOf(names: unknown): string | undefined {
  if (!Array.isArray(names)) return undefined;
  const classes = names.map((name) => TOKEN_CLASSES[String(name)]).filter(Boolean);
  return classes.length > 0 ? classes.join(" ") : undefined;
}

type CodeNode = RootContent | ElementContent;

const lengthOf = (node: CodeNode): number => {
  if (node.type === "text") return node.value.length;
  return node.type === "element" ? node.children.reduce((sum, child) => sum + lengthOf(child), 0) : 0;
};

// Ключ токена — его место в тексте кода: код только дописывается, и прежние токены сохраняют ключи.
function nodesOf(nodes: readonly CodeNode[], start: number): ReactNode[] {
  let at = start;
  return nodes.map((node) => {
    const from = at;
    const length = lengthOf(node);
    at += length;
    if (node.type === "text") return node.value;
    if (node.type !== "element" || length === 0) return null;
    return (
      <span key={from} className={classesOf(node.properties.className)}>
        {nodesOf(node.children, from)}
      </span>
    );
  });
}

/** Код с подсветкой по языку забора; язык, которого грамматики не знают, или его нет — null: код рисуется текстом. */
export function highlightedCode(lang: string, code: string): ReactNode[] | null {
  if (lang === "" || !lowlight.registered(lang)) return null;
  return nodesOf(lowlight.highlight(lang, code).children, 0);
}
