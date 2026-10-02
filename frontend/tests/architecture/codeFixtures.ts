import type { RuleFixture } from "./fixtureTree";

const LOCAL_PAGE = "export const Page = () => null;";

/** Нарушения правил кода: сеть, ключи запросов, lazy, реэкспорты, циклы (план F2, §3.2). */
export const CODE_FIXTURES: readonly RuleFixture[] = [
  {
    rule: "no-raw-http",
    name: "fetch в срезе",
    tree: { "src/features/a/api/load.ts": 'export const load = () => fetch("/v1/a");' },
  },
  {
    rule: "no-raw-http",
    name: "window.fetch в оболочке",
    tree: { "src/shell/ping.ts": 'export const ping = () => window.fetch("/v1/health");' },
  },
  {
    rule: "no-raw-http",
    name: "axios",
    tree: { "src/core/api/client.ts": 'import axios from "axios";\nexport const client = axios;' },
  },
  {
    rule: "query-keys-in-keys-modules",
    name: "литерал queryKey в хуке",
    tree: { "src/features/a/hooks/useA.ts": 'export const options = { queryKey: ["a", 1] };' },
  },
  {
    rule: "query-keys-in-keys-modules",
    name: "литерал mutationKey в хуке",
    tree: { "src/features/a/hooks/useSave.ts": 'export const options = { "mutationKey": ["save"] };' },
  },
  {
    rule: "lazy-in-manifests",
    name: "lazy в сборке",
    tree: {
      "src/composition/Page.tsx": LOCAL_PAGE,
      "src/composition/router.ts": 'import { lazy } from "react";\nexport const P = lazy(() => import("./Page"));',
    },
  },
  {
    rule: "lazy-in-manifests",
    name: "React.lazy в оболочке",
    tree: {
      "src/shell/Page.tsx": LOCAL_PAGE,
      "src/shell/lazyPage.ts": 'import React from "react";\nexport const P = React.lazy(() => import("./Page"));',
    },
  },
  {
    rule: "lazy-in-manifests",
    name: "lazy под другим именем",
    tree: {
      "src/shell/Page.tsx": LOCAL_PAGE,
      "src/shell/lazyPage.ts": 'import { lazy as later } from "react";\nexport const P = later(() => import("./Page"));',
    },
  },
  {
    rule: "no-barrels",
    name: "файл index",
    tree: {
      "src/core/ui/Button.tsx": "export const Button = () => null;",
      "src/core/ui/index.ts": 'export { Button } from "./Button";',
    },
  },
  {
    rule: "no-barrels",
    name: "export * из модуля",
    tree: {
      "src/core/lib/format.ts": "export const format = 1;",
      "src/core/lib/text.ts": 'export * from "./format";',
    },
  },
  {
    rule: "no-cycles",
    name: "два модуля импортируют друг друга",
    tree: {
      "src/core/lib/a.ts": 'import { b } from "./b";\nexport const a = () => b;',
      "src/core/lib/b.ts": 'import { a } from "./a";\nexport const b = () => a;',
    },
  },
  {
    rule: "no-cycles",
    name: "цикл через импорт типа",
    tree: {
      "src/core/lib/a.ts": 'import type { B } from "./b";\nexport type A = B[];',
      "src/core/lib/b.ts": 'import { c } from "./c";\nexport type B = number;\nexport const b = c;',
      "src/core/lib/c.ts": 'import type { A } from "./a";\nexport const c: A = [];',
    },
  },
];
