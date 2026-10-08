import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const SOURCE = /\.(ts|tsx|mjs|css)$/;
const IMPORT =
  /(?:^|[\s;{}])(?:import|export)\s[^'"`;]*?from\s*["']([^"']+)["']|import\s*\(\s*["']([^"']+)["']\s*\)|^\s*import\s*["']([^"']+)["']/gm;

export interface SourceFile {
  /** Путь от корня проекта, например `src/features/notes/ui/notes-screen.tsx`. */
  path: string;
  text: string;
  lines: number;
  /** Все спецификаторы модулей, которые файл импортирует или реэкспортирует, статически или динамически. */
  imports: string[];
}

/** Все исходные файлы в каталоге проекта, прочитанные один раз. */
export function readSources(root: string, directory: string): SourceFile[] {
  const files: SourceFile[] = [];
  const walk = (dir: string) => {
    for (const name of readdirSync(dir)) {
      const path = join(dir, name);
      if (statSync(path).isDirectory()) walk(path);
      else if (SOURCE.test(name)) {
        const text = readFileSync(path, "utf8");
        const lines = text.split("\n").length - (text.endsWith("\n") ? 1 : 0);
        const imports = [...text.matchAll(IMPORT)].map((m) => m[1] ?? m[2] ?? m[3]);
        files.push({ path: relative(root, path), text, lines, imports });
      }
    }
  };
  walk(join(root, directory));
  return files;
}

/** Сгенерированный код не подпадает под лимит длины: каталог генератора или `@generated` в первых 5 строках. */
export const isGenerated = (file: SourceFile) =>
  /(^|\/)(generated|__generated__)\//.test(file.path) ||
  file.text
    .split("\n")
    .slice(0, 5)
    .some((line) => line.includes("@generated"));
