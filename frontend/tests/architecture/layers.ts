import { posix } from "node:path";

/** Слои фронтенда в порядке зависимостей: entrypoints → composition → (shell ∥ features) → core. */
export type Zone = "entrypoints" | "composition" | "shell" | "features" | "core" | "parity-build";

/** Где лежит модуль: слой, срез (для `features/<slice>/`) и первый уровень внутри среза. */
export interface ModulePlace {
  readonly zone: Zone | null;
  readonly slice: string | null;
  readonly sliceArea: string | null;
}

const SOURCE_ZONES: readonly Zone[] = ["entrypoints", "composition", "shell", "features", "core"];

/** Какие слои вправе импортировать модули каждого слоя. Срезы — дополнительно по контрактам. */
export const ALLOWED_TARGETS: Readonly<Record<Zone, ReadonlySet<Zone>>> = {
  entrypoints: new Set(["entrypoints", "composition", "core"]),
  composition: new Set(["composition", "shell", "features", "core"]),
  shell: new Set(["shell", "core"]),
  features: new Set(["features", "core"]),
  core: new Set(["core"]),
  "parity-build": new Set(["parity-build", "composition", "core"]),
};

/** Определяет слой модуля по его пути от `frontend/`. */
export function placeOf(path: string): ModulePlace {
  const parts = path.split("/");
  if (parts[0] === "parity-build") return { zone: "parity-build", slice: null, sliceArea: null };
  const zone = SOURCE_ZONES.find((candidate) => parts[0] === "src" && parts[1] === candidate);
  if (zone === undefined) return { zone: null, slice: null, sliceArea: null };
  if (zone !== "features") return { zone, slice: null, sliceArea: null };
  return { zone, slice: parts[2] ?? null, sliceArea: parts[3] ?? null };
}

/** Путь публичного контракта среза и его манифеста. */
export const sliceContracts = (slice: string): string => `src/features/${slice}/contracts.ts`;
export const sliceManifest = (slice: string): string => `src/features/${slice}/feature.ts`;
export const REGISTRY = "src/composition/registry.ts";

const CANDIDATE_SUFFIXES = ["", ".ts", ".tsx", "/index.ts", "/index.tsx"];

/**
 * Разрешает спецификатор импорта в путь модуля проекта. Возвращает `null` для
 * внешних пакетов и для путей, которых нет среди известных модулей.
 */
export function resolveImport(
  specifier: string,
  fromPath: string,
  knownPaths: ReadonlySet<string>,
): string | null {
  let base: string;
  if (specifier.startsWith("@/")) base = `src/${specifier.slice(2)}`;
  else if (specifier.startsWith("./") || specifier.startsWith("../")) {
    base = posix.normalize(posix.join(posix.dirname(fromPath), specifier));
  } else return null;
  for (const suffix of CANDIDATE_SUFFIXES) {
    if (knownPaths.has(base + suffix)) return base + suffix;
  }
  return null;
}

/** Импорт внешнего пакета `name` или его подпути (`react` → `react/jsx-runtime`). */
export function isPackage(specifier: string, names: ReadonlySet<string>): boolean {
  for (const name of names) {
    if (specifier === name || specifier.startsWith(`${name}/`)) return true;
  }
  return false;
}
