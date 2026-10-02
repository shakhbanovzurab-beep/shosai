// Переписывает таблицы стилей шрифтов из каталога или сверяет их с ним.
//
//   npm run fonts            — переписать src/core/styles/generated/font-roles.css и fonts/roles-*.css
//   npm run fonts -- --check — сверить; код выхода 1 при расхождении
//
// Ту же сверку выполняет `npm test` (tests/styles/fontStylesheets.test.ts).

import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { findDrift, parseFaces, renderFontStylesheets } from "./render.ts";

const FRONTEND_ROOT = fileURLToPath(new URL("../..", import.meta.url));

const readExisting = (path: string): string | null => {
  const file = join(FRONTEND_ROOT, path);
  return existsSync(file) ? readFileSync(file, "utf8") : null;
};

const faces = parseFaces(JSON.parse(readFileSync(join(FRONTEND_ROOT, "fonts/faces.json"), "utf8")));
const files = renderFontStylesheets(faces);

if (process.argv.includes("--check")) {
  const drift = findDrift(files, readExisting);
  for (const path of drift) console.error(`✗ ${path} разошёлся с каталогом шрифтов`);
  if (drift.length > 0) {
    console.error("Перепишите файлы: npm run fonts");
    process.exitCode = 1;
  } else {
    console.log(`✓ ${files.size} таблиц стилей шрифтов совпадают с каталогом`);
  }
} else {
  for (const [path, text] of files) {
    const file = join(FRONTEND_ROOT, path);
    mkdirSync(dirname(file), { recursive: true });
    writeFileSync(file, text);
  }
  console.log(`✓ Переписано таблиц стилей шрифтов: ${files.size}`);
}
