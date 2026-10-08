import { dirname, join, normalize } from "node:path";

export const LAYERS = ["domain", "data", "api", "model", "ui", "mocks"] as const;
export type Layer = (typeof LAYERS)[number];

export type Location =
  | { kind: "feature"; slice: string; layer: Layer | null }
  | { kind: "app" }
  | { kind: "mocks" }
  | { kind: "entry" }
  | { kind: "scripts" }
  | { kind: "shared" };

/** Где лежит путь под src/: слайс и его слой, маршрутизация, моки API, точка входа, инструменты или общий код. */
export function locate(path: string): Location {
  const parts = path.split("/");
  if (parts[1] === "app") return { kind: "app" };
  if (parts[1] === "mocks") return { kind: "mocks" };
  if (parts[1] === "scripts") return { kind: "scripts" };
  if (parts[1] === "main.tsx") return { kind: "entry" };
  if (parts[1] !== "features") return { kind: "shared" };
  const layer = parts[3] as Layer;
  return { kind: "feature", slice: parts[2], layer: LAYERS.includes(layer) ? layer : null };
}

/** Путь в проекте, на который указывает спецификатор, или null для пакета. */
export function resolveSpecifier(fromFile: string, specifier: string): string | null {
  if (specifier.startsWith("@/")) return `src/${specifier.slice(2)}`;
  if (specifier.startsWith(".")) return normalize(join(dirname(fromFile), specifier));
  return null;
}
