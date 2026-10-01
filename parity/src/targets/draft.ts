// Цель «черновик»: сборка его фронтенда и статика его бэкенда из экспорта на
// закреплённом коммите (scripts/export-draft.sh, scripts/build-draft.sh).

import { existsSync } from "node:fs";
import path from "node:path";

import type { ParityConfig } from "../config.ts";
import type { SiteFiles } from "../serve/site.ts";

export function draftSite(config: ParityConfig): SiteFiles {
  const files: SiteFiles = {
    appDir: path.join(config.draftExport, "dist"),
    fontDirs: [
      path.join(config.draftExport, "backend", "static", "landing", "fonts"),
      path.join(config.draftExport, "backend", "static", "webfonts"),
    ],
    rootDir: path.join(config.draftExport, "backend", "static"),
  };
  if (!existsSync(path.join(files.appDir, "index.html"))) {
    throw new Error(`Сборки черновика нет в ${files.appDir}: запустите scripts/build-draft.sh`);
  }
  return files;
}
