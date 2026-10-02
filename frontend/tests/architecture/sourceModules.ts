import { parseSync, Visitor, type ESTree } from "vite";

/** Исходный файл проекта: путь от `frontend/` через «/» и текст. */
export interface SourceFile {
  readonly path: string;
  readonly text: string;
}

/** Один импорт модуля: статический, реэкспорт или динамический `import()`. */
export interface ImportEdge {
  readonly specifier: string;
  readonly line: number;
  readonly typeOnly: boolean;
  readonly dynamic: boolean;
}

/** Факты о модуле, которые читают архитектурные правила. */
export interface SourceModule {
  readonly path: string;
  readonly imports: readonly ImportEdge[];
  readonly starReexportLines: readonly number[];
  readonly fetchCallLines: readonly number[];
  readonly lazyCallLines: readonly number[];
  readonly literalKeyLines: readonly number[];
}

// Глобальные объекты, через которые доступен `fetch` без импорта.
const GLOBAL_OBJECTS = new Set(["window", "globalThis", "self"]);
const KEY_PROPERTIES = new Set(["queryKey", "mutationKey"]);

/** Разбирает модуль парсером oxc, который поставляется с Vite, и собирает факты. */
export function analyzeModule(file: SourceFile): SourceModule {
  const result = parseSync(file.path, file.text);
  const firstError = result.errors[0];
  if (firstError !== undefined) {
    throw new Error(`${file.path}: не разбирается — ${firstError.message}`);
  }
  const lineOf = lineLocator(file.text);
  const reactBindings = collectReactBindings(result.module.staticImports);

  const imports: ImportEdge[] = result.module.staticImports.map((entry) => ({
    specifier: entry.moduleRequest.value,
    line: lineOf(entry.start),
    typeOnly: entry.entries.length > 0 && entry.entries.every((binding) => binding.isType),
    dynamic: false,
  }));
  const starReexportLines: number[] = [];
  for (const declaration of result.module.staticExports) {
    for (const entry of declaration.entries) {
      if (entry.moduleRequest === null) continue;
      imports.push({
        specifier: entry.moduleRequest.value,
        line: lineOf(entry.start),
        typeOnly: entry.isType,
        dynamic: false,
      });
      if (entry.importName.kind === "All" || entry.importName.kind === "AllButDefault") {
        starReexportLines.push(lineOf(entry.start));
      }
    }
  }
  for (const entry of result.module.dynamicImports) {
    const specifier = literalText(file.text.slice(entry.moduleRequest.start, entry.moduleRequest.end));
    if (specifier === null) continue;
    imports.push({ specifier, line: lineOf(entry.start), typeOnly: false, dynamic: true });
  }

  const fetchCallLines: number[] = [];
  const lazyCallLines: number[] = [];
  const literalKeyLines: number[] = [];
  new Visitor({
    CallExpression(node) {
      if (isFetchCallee(node.callee)) fetchCallLines.push(lineOf(node.start));
      if (isLazyCallee(node.callee, reactBindings)) lazyCallLines.push(lineOf(node.start));
    },
    Property(node) {
      if (node.type !== "Property" || node.computed) return;
      if (!("value" in node) || node.value.type !== "ArrayExpression") return;
      const name = propertyName(node.key);
      if (name !== null && KEY_PROPERTIES.has(name)) literalKeyLines.push(lineOf(node.start));
    },
  }).visit(result.program);

  return {
    path: file.path,
    imports,
    starReexportLines,
    fetchCallLines,
    lazyCallLines,
    literalKeyLines,
  };
}

interface ReactBindings {
  readonly lazyNames: ReadonlySet<string>;
  readonly namespaces: ReadonlySet<string>;
}

type StaticImports = ReturnType<typeof parseSync>["module"]["staticImports"];

// Локальные имена, под которыми модуль видит `lazy` из React: `import { lazy as l }`
// и `import React from "react"` / `import * as React from "react"`.
function collectReactBindings(staticImports: StaticImports): ReactBindings {
  const lazyNames = new Set<string>();
  const namespaces = new Set<string>();
  for (const declaration of staticImports) {
    if (declaration.moduleRequest.value !== "react") continue;
    for (const binding of declaration.entries) {
      const imported = binding.importName;
      if (imported.kind === "Name" && imported.name === "lazy") lazyNames.add(binding.localName.value);
      if (imported.kind === "Default" || imported.kind === "NamespaceObject") {
        namespaces.add(binding.localName.value);
      }
    }
  }
  return { lazyNames, namespaces };
}

function isFetchCallee(callee: ESTree.Expression): boolean {
  if (callee.type === "Identifier") return callee.name === "fetch";
  if (callee.type !== "MemberExpression" || callee.computed) return false;
  return (
    callee.property.type === "Identifier" &&
    callee.property.name === "fetch" &&
    callee.object.type === "Identifier" &&
    GLOBAL_OBJECTS.has(callee.object.name)
  );
}

function isLazyCallee(callee: ESTree.Expression, react: ReactBindings): boolean {
  if (callee.type === "Identifier") return react.lazyNames.has(callee.name);
  if (callee.type !== "MemberExpression" || callee.computed) return false;
  return (
    callee.property.type === "Identifier" &&
    callee.property.name === "lazy" &&
    callee.object.type === "Identifier" &&
    react.namespaces.has(callee.object.name)
  );
}

function propertyName(key: ESTree.PropertyKey): string | null {
  if (key.type === "Identifier") return key.name;
  if (key.type === "Literal" && typeof key.value === "string") return key.value;
  return null;
}

// Спецификатор динамического импорта учитывается, только если это строковый
// литерал: путь из шаблона статически не известен.
function literalText(source: string): string | null {
  const quote = source[0];
  if ((quote !== '"' && quote !== "'") || source.at(-1) !== quote) return null;
  return source.slice(1, -1);
}

// Номер строки по смещению в тексте (смещения oxc — в единицах UTF-16).
function lineLocator(text: string): (offset: number) => number {
  const starts = [0];
  for (let index = text.indexOf("\n"); index !== -1; index = text.indexOf("\n", index + 1)) {
    starts.push(index + 1);
  }
  return (offset) => {
    let low = 0;
    let high = starts.length - 1;
    while (low < high) {
      const middle = (low + high + 1) >> 1;
      if ((starts[middle] ?? 0) <= offset) low = middle;
      else high = middle - 1;
    }
    return low + 1;
  };
}
