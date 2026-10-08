import { type Layer, type Location, locate, resolveSpecifier } from "./locate";

/** Для каждого слоя — слои того же слайса, которые он может импортировать. */
const INNER: Record<Layer, readonly Layer[]> = {
  domain: ["domain"],
  data: ["domain", "data"],
  api: ["domain", "api"],
  model: ["domain", "data", "api", "model"],
  ui: ["domain", "data", "model", "ui"],
  mocks: ["domain", "data", "mocks"],
};
/** Слои бизнес-ядра и транспорта: без фреймворка, интерфейса и других слайсов. */
const PURE: readonly Layer[] = ["domain", "data", "api"];
/** Пакеты, привязывающие код к React, роутеру, интерфейсу или хранилищу. */
const FRAMEWORK =
  /^(react|react-dom|react-router|@tanstack\/react-query|use-intl|zustand|sonner|lucide-react|framer-motion|recharts|radix-ui|cmdk|vaul)(\/|$)/;
const PURE_BANNED =
  /^@\/(components|hooks|app)\/|^@\/lib\/(polling-resource|copy-text|navigation|lazy-component|.*\.client)$/;
/** Next.js ушёл из кабинета с переходом на Vite (ADR 0021). */
const NEXT = /^(next|next-intl|next-themes|server-only)(\/|$)/;

type Report = (message: string) => void;

function checkPackage(file: string, from: Location, specifier: string, report: Report) {
  if (NEXT.test(specifier)) report(`imports "${specifier}"; the cabinet is a Vite app (ADR 0021)`);
  if (/^msw(\/|$)/.test(specifier) && from.kind !== "mocks" && !file.endsWith(".test.ts"))
    report(`imports "${specifier}" outside src/mocks and tests; mocks never reach a production build`);
  if (from.kind === "feature" && from.layer && PURE.includes(from.layer) && FRAMEWORK.test(specifier))
    report(`${from.layer} must not depend on "${specifier}"`);
}

/**
 * Проверяет один импорт одного файла. `edge` записывает зависимость между двумя слайсами (вне моков) для
 * проверки циклов.
 */
export function checkImport(file: string, specifier: string, report: Report, edge: (to: string) => void) {
  const from = locate(file);
  const targetPath = resolveSpecifier(file, specifier);
  if (targetPath === null) return checkPackage(file, from, specifier, report);
  const target = locate(targetPath);
  const pure = from.kind === "feature" && from.layer !== null && PURE.includes(from.layer);
  if (pure && PURE_BANNED.test(specifier))
    return report(`${from.kind === "feature" ? from.layer : ""} must not depend on "${specifier}"`);

  if (target.kind === "app" && !["app", "entry", "mocks"].includes(from.kind))
    return report(`imports routing (${specifier}); only the entry and the mocks may`);
  if (
    target.kind === "mocks" &&
    !["mocks", "entry"].includes(from.kind) &&
    !(from.kind === "feature" && from.layer === "mocks")
  )
    return report(`imports the mock API (${specifier}) outside the mocks`);
  if (from.kind === "shared" && target.kind === "feature")
    return report(`shared code must not import features (${specifier})`);
  if (from.kind === "feature" && from.layer === null) return report("is outside the slice layers");
  if (target.kind !== "feature") {
    if (
      from.kind === "feature" &&
      from.layer !== "ui" &&
      from.layer !== "mocks" &&
      specifier.startsWith("@/components/")
    )
      report(`${from.layer} must not import UI components (${specifier})`);
    return;
  }
  if (target.layer === null) return report(`imports outside ${target.slice}'s layers (${specifier})`);

  const fromMocks = from.kind === "mocks" || (from.kind === "feature" && from.layer === "mocks");
  if (target.layer === "mocks" && !fromMocks)
    return report(`imports ${target.slice}'s mocks (${specifier}) outside the mocks`);
  if (from.kind !== "feature") return;

  if (from.slice !== target.slice) {
    if (pure) return report(`${from.layer} must not import other slices (${specifier})`);
    if (from.layer !== "mocks") edge(target.slice);
    return;
  }
  if (!from.layer || !INNER[from.layer].includes(target.layer))
    report(`${from.layer} must not import ${target.layer} (${specifier})`);
}
