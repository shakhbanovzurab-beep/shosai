import type { RuleFixture } from "./fixtureTree";

const SHELL_FRAME = { "src/shell/Frame.tsx": "export const Frame = () => null;" };
const SLICE_B = {
  "src/features/b/feature.ts": "export const feature = {};",
  "src/features/b/contracts.ts": "export type B = number;",
  "src/features/b/model/b.ts": "export const b = 1;",
  "src/features/b/ui/BView.tsx": "export const BView = () => null;",
};

/** Нарушения границ: слои, контракты срезов, оболочка, чистая модель, UI без HTTP (план F2, §3.2). */
export const BOUNDARY_FIXTURES: readonly RuleFixture[] = [
  {
    rule: "layers",
    name: "ядро импортирует оболочку",
    tree: { ...SHELL_FRAME, "src/core/lib/a.ts": 'import { Frame } from "@/shell/Frame";\nexport const a = Frame;' },
  },
  {
    rule: "layers",
    name: "оболочка импортирует сборку",
    tree: {
      "src/composition/registry.ts": "export const registry = [];",
      "src/shell/Frame.tsx": 'import { registry } from "@/composition/registry";\nexport const Frame = () => registry;',
    },
  },
  {
    rule: "layers",
    name: "срез импортирует оболочку",
    tree: { ...SHELL_FRAME, "src/features/a/ui/A.tsx": 'import { Frame } from "@/shell/Frame";\nexport const A = Frame;' },
  },
  {
    rule: "layers",
    name: "сборка импортирует точку входа",
    tree: {
      "src/entrypoints/main.tsx": "export const started = true;",
      "src/composition/boot.ts": 'import { started } from "@/entrypoints/main";\nexport const boot = started;',
    },
  },
  { rule: "layers", name: "модуль вне слоёв", tree: { "src/helpers/format.ts": "export const format = 1;" } },
  {
    rule: "layers",
    name: "сборка паритета импортирует срез",
    tree: { ...SLICE_B, "parity-build/standIns.ts": 'import type { B } from "@/features/b/contracts";\nexport type S = B;' },
  },
  {
    rule: "slice-contracts",
    name: "срез читает модель чужого среза",
    tree: { ...SLICE_B, "src/features/a/ui/A.tsx": 'import { b } from "@/features/b/model/b";\nexport const A = b;' },
  },
  {
    rule: "slice-contracts",
    name: "срез импортирует чужой манифест",
    tree: { ...SLICE_B, "src/features/a/api/a.ts": 'import { feature } from "@/features/b/feature";\nexport const a = feature;' },
  },
  {
    rule: "slice-contracts",
    name: "манифест импортирует не реестр",
    tree: { ...SLICE_B, "src/composition/router.ts": 'import { feature } from "@/features/b/feature";\nexport const r = feature;' },
  },
  {
    rule: "slice-contracts",
    name: "срез импортирует собственный манифест",
    tree: { ...SLICE_B, "src/features/b/screens/S.tsx": 'import { feature } from "../feature";\nexport const S = feature;' },
  },
  {
    rule: "slice-contracts",
    name: "сборка лезет во внутренности среза",
    tree: { ...SLICE_B, "src/composition/router.ts": 'export const load = () => import("@/features/b/ui/BView");' },
  },
  {
    rule: "shell-knows-no-slice",
    name: "оболочка импортирует контракт среза",
    tree: { ...SLICE_B, "src/shell/Sidebar.tsx": 'import type { B } from "@/features/b/contracts";\nexport type S = B;' },
  },
  {
    rule: "pure-model",
    name: "модель импортирует React",
    tree: { "src/features/a/model/m.ts": 'import type { ReactNode } from "react";\nexport type M = ReactNode;' },
  },
  {
    rule: "pure-model",
    name: "модель импортирует клиент API",
    tree: {
      "src/core/api/client.ts": "export const client = {};",
      "src/features/a/model/m.ts": 'import { client } from "@/core/api/client";\nexport const m = client;',
    },
  },
  {
    rule: "pure-model",
    name: "модель импортирует компонент своего среза",
    tree: {
      "src/features/a/ui/View.tsx": "export const View = () => null;",
      "src/features/a/model/m.ts": 'import { View } from "../ui/View";\nexport const m = View;',
    },
  },
  {
    rule: "ui-without-http",
    name: "компонент среза импортирует его API",
    tree: {
      "src/features/a/api/load.ts": "export const load = 1;",
      "src/features/a/ui/A.tsx": 'import { load } from "../api/load";\nexport const A = load;',
    },
  },
  {
    rule: "ui-without-http",
    name: "компонент ядра импортирует клиент API",
    tree: {
      "src/core/api/client.ts": "export const client = {};",
      "src/core/ui/Button.tsx": 'import { client } from "@/core/api/client";\nexport const Button = client;',
    },
  },
  {
    rule: "ui-without-http",
    name: "компонент ядра импортирует HTTP-клиент",
    tree: { "src/core/ui/Button.tsx": 'import createClient from "openapi-fetch";\nexport const Button = createClient;' },
  },
];
