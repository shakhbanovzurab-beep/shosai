import { checkImport } from "./import-rules";
import { locate } from "./locate";
import { isGenerated, readSources } from "./source-files";
import { resolve } from "node:path";

const ROOT = resolve(import.meta.dirname, "../../..");
const MAX_LINES = 200;
const REEXPORT = /^\s*export\s+(type\s+)?(\*|\{[^}]*\})\s+from\s/m;

/**
 * Все нарушения структуры кабинета (docs/architecture.md) строками «файл: сообщение»: лимит 200 строк,
 * никаких barrel-файлов и реэкспортов (F2-D4), слои слайсов и их импорты, никаких циклов между слайсами.
 */
export function findArchitectureProblems(): string[] {
  const problems: string[] = [];
  const edges = new Map<string, Set<string>>();
  for (const file of [...readSources(ROOT, "src"), ...readSources(ROOT, "tooling")]) {
    const report = (message: string) => problems.push(`${file.path}: ${message}`);
    if (file.lines > MAX_LINES && !isGenerated(file)) report(`${file.lines} lines, over the ${MAX_LINES}-line limit`);
    if (file.path.endsWith(".css") || file.path.startsWith("tooling/")) continue;
    if (/\/index\.(ts|tsx)$/.test(file.path)) report("is an index module; import the defining module instead (F2-D4)");
    if (REEXPORT.test(file.text)) report("re-exports another module; import the defining module instead (F2-D4)");
    if (locate(file.path.replace(/^/, "")).kind === "scripts") continue;
    const from = locate(file.path);
    for (const specifier of file.imports)
      checkImport(file.path, specifier, report, (to) => {
        if (from.kind !== "feature") return;
        if (!edges.has(from.slice)) edges.set(from.slice, new Set());
        edges.get(from.slice)?.add(to);
      });
  }
  // Слайсы зависят друг от друга только в одну сторону.
  const visit = (slice: string, trail: string[]) => {
    if (trail.includes(slice))
      return void problems.push(`slice cycle: ${[...trail.slice(trail.indexOf(slice)), slice].join(" → ")}`);
    for (const next of edges.get(slice) ?? []) visit(next, [...trail, slice]);
  };
  for (const slice of edges.keys()) visit(slice, []);
  return [...new Set(problems)];
}
