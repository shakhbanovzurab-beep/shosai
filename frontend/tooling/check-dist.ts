// Проверка production-сборки (npm run build): в dist нет моков и карт исходников, есть хеши встроенных скриптов,
// JS укладывается в бюджет (замер 2026-10-08: начальный JS 197 КБ gzip, крупнейший чанк — редактор заметок, 152 КБ).
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { gzipSync } from "node:zlib";

const DIST = fileURLToPath(new URL("../dist", import.meta.url));
const KB = 1024;
// JS, который index.html загружает сразу (вход и modulepreload), и любой отдельный чанк — в gzip.
const INITIAL_BUDGET = 220 * KB;
const CHUNK_BUDGET = 170 * KB;
const gzipSize = (path: string) => gzipSync(readFileSync(path), { level: 9 }).length;
// Признаки моков: адрес воркера MSW (строка в src/mocks/browser.ts) и префикс сообщений библиотеки.
const MOCK_MARKERS = ["mockServiceWorker", "[MSW]"];

const files: string[] = [];
const walk = (dir: string) => {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) walk(path);
    else files.push(path);
  }
};
walk(DIST);

const problems: string[] = [];
for (const file of files) {
  const name = relative(DIST, file);
  if (name.endsWith(".map")) problems.push(`${name}: source maps are not published`);
  if (!/\.(js|html)$/.test(name)) continue;
  const text = readFileSync(file, "utf8");
  for (const marker of MOCK_MARKERS)
    if (text.includes(marker)) problems.push(`${name}: contains mock code (${marker})`);
}
if (!existsSync(join(DIST, "csp-hashes.json"))) problems.push("csp-hashes.json is missing");

const html = readFileSync(join(DIST, "index.html"), "utf8");
const initial = [...html.matchAll(/(?:src|href)="\/app\/(assets\/[^"]+\.js)"/g)].map((match) => match[1]);
const initialSize = initial.reduce((sum, file) => sum + gzipSize(join(DIST, file)), 0);
if (initialSize > INITIAL_BUDGET)
  problems.push(`initial JS is ${Math.round(initialSize / KB)} KB gzip, budget ${INITIAL_BUDGET / KB} KB`);
for (const file of files.filter((path) => path.endsWith(".js"))) {
  const size = gzipSize(file);
  if (size > CHUNK_BUDGET)
    problems.push(`${relative(DIST, file)}: ${Math.round(size / KB)} KB gzip, budget ${CHUNK_BUDGET / KB} KB`);
}

for (const problem of problems) console.error(problem);
if (problems.length > 0) process.exit(1);
console.log(
  `dist: ${files.length} files, no mocks, no source maps, initial JS ${Math.round(initialSize / KB)} KB gzip`,
);
