import { findCycles } from "./cycles";
import { edgeViolation } from "./edgeRules";
import { resolveImport } from "./layers";
import { moduleViolations } from "./moduleRules";
import { analyzeModule, type SourceFile } from "./sourceModules";
import type { Violation } from "./violations";

/** Проверяет дерево исходников на все правила архитектуры и возвращает нарушения. */
export function checkArchitecture(files: readonly SourceFile[]): Violation[] {
  const modules = files.map(analyzeModule);
  const knownPaths = new Set(modules.map((module) => module.path));
  const violations: Violation[] = [];
  const graph = new Map<string, string[]>();

  for (const module of modules) {
    violations.push(...moduleViolations(module));
    const targets: string[] = [];
    for (const edge of module.imports) {
      const target = resolveImport(edge.specifier, module.path, knownPaths);
      const finding = edgeViolation({ from: module.path, edge, target });
      if (finding !== null) violations.push({ ...finding, path: module.path, line: edge.line });
      // Динамический импорт цикла не создаёт: модуль грузится позже, по требованию.
      if (target !== null && !edge.dynamic) targets.push(target);
    }
    graph.set(module.path, targets);
  }

  for (const cycle of findCycles(graph)) {
    violations.push({ rule: "no-cycles", path: cycle[0] ?? "", line: 1, detail: cycle.join(" ↔ ") });
  }
  return violations;
}
