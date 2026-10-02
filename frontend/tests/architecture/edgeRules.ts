import {
  ALLOWED_TARGETS,
  isPackage,
  placeOf,
  REGISTRY,
  sliceContracts,
  sliceManifest,
  type ModulePlace,
} from "./layers";
import type { ImportEdge } from "./sourceModules";
import type { RuleId } from "./violations";

/** Импорт модуля: `target` — путь модуля проекта или `null` для внешнего пакета. */
export interface ResolvedEdge {
  readonly from: string;
  readonly edge: ImportEdge;
  readonly target: string | null;
}

/** Нарушение без места: место — строка импорта, его подставляет вызывающий. */
export interface EdgeFinding {
  readonly rule: RuleId;
  readonly detail: string;
}

// Пакеты React, роутера, запросов и HTTP: чистой модели среза они запрещены.
const IMPURE_PACKAGES = new Set([
  "react",
  "react-dom",
  "react-router",
  "react-i18next",
  "@tanstack/react-query",
  "zustand",
  "openapi-fetch",
]);
const HTTP_CLIENT_PACKAGES = new Set(["openapi-fetch"]);
const FORBIDDEN_HTTP_PACKAGES = new Set(["axios"]);
// Модули ядра, которые тянут за собой React, запросы или HTTP.
const IMPURE_CORE_PREFIXES = ["src/core/api/", "src/core/ui/", "src/core/query/", "src/core/hooks/"];
// Части своего среза, которые недоступны его чистой модели.
const IMPURE_SLICE_AREAS = new Set(["api", "state", "hooks", "ui", "screens"]);

/**
 * Первое правило, которое нарушает импорт, или `null`. На один импорт — не
 * больше одного нарушения, чтобы отчёт называл причину, а не её следствия.
 */
export function edgeViolation({ from, edge, target }: ResolvedEdge): EdgeFinding | null {
  const source = placeOf(from);
  // Модуль вне слоёв помечается один раз правилом модуля, а не на каждом импорте.
  if (source.zone === null) return null;
  const specifier = edge.specifier;
  if (target === null) return externalViolation(from, source, specifier);

  const destination = placeOf(target);
  if (destination.zone === null) return null;
  if (source.zone === "shell" && destination.zone === "features") {
    return { rule: "shell-knows-no-slice", detail: specifier };
  }
  if (!ALLOWED_TARGETS[source.zone].has(destination.zone)) {
    return { rule: "layers", detail: `${source.zone} → ${destination.zone}: ${specifier}` };
  }
  if (destination.zone === "features" && destination.slice !== null) {
    const reason = sliceContractViolation(from, source, target, destination.slice);
    if (reason !== null) return { rule: "slice-contracts", detail: `${reason}: ${specifier}` };
  }
  if (isModel(source) && isImpureForModel(source, target, destination)) {
    return { rule: "pure-model", detail: specifier };
  }
  if (isUi(from, source) && isApiModule(target, destination)) {
    return { rule: "ui-without-http", detail: specifier };
  }
  return null;
}

function externalViolation(from: string, source: ModulePlace, specifier: string): EdgeFinding | null {
  if (isPackage(specifier, FORBIDDEN_HTTP_PACKAGES)) {
    return { rule: "no-raw-http", detail: `${specifier}: HTTP — только через core/api` };
  }
  if (isModel(source) && isPackage(specifier, IMPURE_PACKAGES)) {
    return { rule: "pure-model", detail: specifier };
  }
  if (isUi(from, source) && isPackage(specifier, HTTP_CLIENT_PACKAGES)) {
    return { rule: "ui-without-http", detail: specifier };
  }
  return null;
}

function sliceContractViolation(
  from: string,
  source: ModulePlace,
  target: string,
  slice: string,
): string | null {
  if (target === sliceManifest(slice)) {
    return from === REGISTRY ? null : "манифест среза импортирует только реестр";
  }
  if (source.zone === "features" && source.slice === slice) return null;
  if (target === sliceContracts(slice)) return null;
  return "чужой срез доступен только через contracts.ts";
}

const isModel = (place: ModulePlace): boolean =>
  place.zone === "features" && place.sliceArea === "model";

function isImpureForModel(source: ModulePlace, target: string, destination: ModulePlace): boolean {
  if (target.endsWith(".tsx")) return true;
  if (IMPURE_CORE_PREFIXES.some((prefix) => target.startsWith(prefix))) return true;
  return (
    destination.zone === "features" &&
    destination.slice === source.slice &&
    destination.sliceArea !== null &&
    IMPURE_SLICE_AREAS.has(destination.sliceArea)
  );
}

const isUi = (path: string, place: ModulePlace): boolean =>
  path.startsWith("src/core/ui/") || (place.zone === "features" && place.sliceArea === "ui");

const isApiModule = (target: string, destination: ModulePlace): boolean =>
  target.startsWith("src/core/api/") ||
  (destination.zone === "features" && destination.sliceArea === "api");
