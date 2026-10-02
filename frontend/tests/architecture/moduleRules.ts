import { posix } from "node:path";

import { placeOf } from "./layers";
import type { SourceModule } from "./sourceModules";
import type { Violation } from "./violations";

// Сеть напрямую — только клиенту API и пробе связи; разделы ходят через клиент.
const RAW_HTTP_HOSTS = ["src/core/api/", "src/core/connection/"];
const MANIFEST_PATTERN = /^src\/features\/[^/]+\/feature\.ts$/;
const LAZY_HELPERS_PREFIX = "src/core/feature/";
const BARREL_NAMES = new Set(["index.ts", "index.tsx"]);
const KEYS_MODULE_NAME = "keys.ts";

/** Нарушения, которые видны по самому модулю, без его импортов. */
export function moduleViolations(module: SourceModule): Violation[] {
  const { path } = module;
  const name = posix.basename(path);
  const found: Violation[] = [];
  const add = (rule: Violation["rule"], line: number, detail: string): void => {
    found.push({ rule, path, line, detail });
  };

  if (placeOf(path).zone === null) {
    add("layers", 1, "модуль вне слоёв entrypoints, composition, shell, features, core");
  }
  if (BARREL_NAMES.has(name)) add("no-barrels", 1, "файл index — точка реэкспорта");
  for (const line of module.starReexportLines) add("no-barrels", line, "export * из другого модуля");

  if (!RAW_HTTP_HOSTS.some((prefix) => path.startsWith(prefix))) {
    for (const line of module.fetchCallLines) add("no-raw-http", line, "fetch вне core/api и пробы связи");
  }
  if (name !== KEYS_MODULE_NAME) {
    for (const line of module.literalKeyLines) {
      add("query-keys-in-keys-modules", line, "литерал ключа запроса вне модуля keys.ts");
    }
  }
  if (!MANIFEST_PATTERN.test(path) && !path.startsWith(LAZY_HELPERS_PREFIX)) {
    for (const line of module.lazyCallLines) add("lazy-in-manifests", line, "lazy() вне манифеста среза");
  }
  return found;
}
