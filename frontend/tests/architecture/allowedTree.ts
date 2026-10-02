import type { FixtureTree } from "./fixtureTree";

/**
 * Дерево, где есть каждая законная связь: слои сверху вниз, реестр → манифест,
 * срез → контракт другого среза, сеть в core/api и пробе связи, ключи в keys.ts,
 * lazy в манифесте и помощнике ядра, цикл только через динамический импорт.
 * Ни одно правило здесь срабатывать не должно.
 */
export const ALLOWED_TREE: FixtureTree = {
  "src/entrypoints/main.tsx":
    'import { AppRoot } from "@/composition/AppRoot";\nimport { cn } from "@/core/lib/cn";\nexport const app = [AppRoot, cn];',
  "src/composition/registry.ts":
    'import { feature as a } from "@/features/a/feature";\nimport { feature as b } from "@/features/b/feature";\nexport const registry = [a, b];',
  "src/composition/AppRoot.tsx":
    'import { registry } from "./registry";\nimport { Frame } from "@/shell/Frame";\nexport const AppRoot = () => [registry, Frame];',
  "src/shell/Frame.tsx": 'import { Button } from "@/core/ui/Button";\nexport const Frame = () => Button;',
  "src/core/lib/cn.ts": "export const cn = (...names: string[]) => names.join(' ');",
  "src/core/ui/Button.tsx": 'import { cn } from "@/core/lib/cn";\nexport const Button = () => cn("button");',
  "src/core/api/client.ts": 'export const request = (path: string) => fetch(`/v1${path}`);',
  "src/core/connection/probe.ts": 'export const probe = () => globalThis.fetch("/v1/health");',
  "src/core/feature/lazyScreen.ts":
    'import { lazy } from "react";\nexport const lazyScreen = (load: Parameters<typeof lazy>[0]) => lazy(load);',
  "src/core/lib/later.ts": 'export const later = () => import("./now");',
  "src/core/lib/now.ts": 'import { later } from "./later";\nexport const now = later;',
  "src/features/a/feature.ts":
    'import { lazy } from "react";\nexport const feature = { screen: lazy(() => import("./screens/AScreen")) };',
  "src/features/a/screens/AScreen.tsx":
    'import { useA } from "../hooks/useA";\nimport { AView } from "../ui/AView";\nimport type { B } from "@/features/b/contracts";\nexport default function AScreen() { const b: B = 1; return [useA, AView, b]; }',
  "src/features/a/hooks/useA.ts":
    'import { aKeys } from "../api/keys";\nimport { loadA } from "../api/loadA";\nexport const useA = () => ({ queryKey: aKeys.all, queryFn: loadA });',
  "src/features/a/api/keys.ts": 'export const aKeys = { all: ["a"] as const };\nexport const first = { queryKey: ["a", 1] };',
  "src/features/a/api/loadA.ts": 'import { request } from "@/core/api/client";\nexport const loadA = () => request("/a");',
  "src/features/a/model/total.ts":
    'import { cn } from "@/core/lib/cn";\nimport type { B } from "@/features/b/contracts";\nexport const total = (items: B[]) => cn(String(items.length));',
  "src/features/a/ui/AView.tsx": 'import { total } from "../model/total";\nexport const AView = () => total([]);',
  "src/features/b/feature.ts": "export const feature = {};",
  "src/features/b/contracts.ts": 'export type { B } from "./model/b";',
  "src/features/b/model/b.ts": "export type B = number;",
  "parity-build/entry.tsx":
    'import { registry } from "@/composition/registry";\nimport { cn } from "@/core/lib/cn";\nexport const standIns = [registry, cn];',
};
