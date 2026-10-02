import { globSync, readFileSync } from "node:fs";
import { join } from "node:path";

/** Каталог `frontend/`. */
export const FRONTEND_ROOT = join(import.meta.dirname, "../..");

export interface Stylesheet {
  /** Путь от `frontend/`. */
  readonly path: string;
  readonly text: string;
}

/** Таблицы стилей проекта по шаблону от `frontend/`. */
export function readStylesheets(pattern: string): Stylesheet[] {
  return globSync(pattern, { cwd: FRONTEND_ROOT })
    .toSorted()
    .map((path) => ({ path, text: readFileSync(join(FRONTEND_ROOT, path), "utf8") }));
}

/** Текст без комментариев: правила разбираются по нему. */
export const withoutComments = (css: string): string => css.replace(/\/\*[\s\S]*?\*\//g, "");

/** Объявления custom properties внутри блоков, чей селектор совпал с `selector`. */
export function declaredIn(css: string, selector: RegExp): Set<string> {
  const names = new Set<string>();
  for (const block of withoutComments(css).matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    if (!selector.test((block[1] ?? "").trim())) continue;
    for (const declaration of (block[2] ?? "").matchAll(/(--[\w-]+)\s*:/g)) names.add(declaration[1] ?? "");
  }
  return names;
}

/**
 * Жалобы на разбираемость: незакрытый комментарий, лишняя закрывающая пара,
 * несбалансированные скобки. Раскол большой таблицы — вырезание кусков текста,
 * и такая ошибка молча уносит соседнее правило.
 */
export function syntaxComplaints({ path, text }: Stylesheet): string[] {
  const complaints: string[] = [];
  let depth = 0;
  let index = 0;
  while (index < text.length) {
    if (text.startsWith("/*", index)) {
      const end = text.indexOf("*/", index + 2);
      if (end === -1) return [...complaints, `${path}: комментарий не закрыт`];
      index = end + 2;
      continue;
    }
    if (text.startsWith("*/", index)) complaints.push(`${path}: */ без открывающего /*`);
    const char = text[index];
    if (char === '"' || char === "'") {
      const close = text.indexOf(char, index + 1);
      index = close === -1 ? text.length : close + 1;
      continue;
    }
    if (char === "{") depth += 1;
    if (char === "}") depth -= 1;
    if (depth < 0) {
      complaints.push(`${path}: лишняя закрывающая }`);
      depth = 0;
    }
    index += 1;
  }
  return depth === 0 ? complaints : [...complaints, `${path}: не закрыто скобок: ${depth}`];
}
