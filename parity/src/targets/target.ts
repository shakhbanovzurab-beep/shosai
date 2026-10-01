// Цель съёмки: какой фронтенд рисует экран. Эталон снимается с черновика,
// сравнение — с v2; данные у обоих одни и те же (fixtures/).

import { existsSync } from "node:fs";
import path from "node:path";

import type { ParityConfig } from "../config.ts";
import type { SiteFiles } from "../serve/site.ts";
import { draftSite } from "./draft.ts";

export type TargetName = "draft" | "v2";

export function parseTarget(value: string | undefined): TargetName {
  if (value === "draft" || value === "v2") return value;
  throw new Error(`PARITY_TARGET должен быть draft или v2, получено: ${value ?? "ничего"}`);
}

function v2Site(config: ParityConfig): SiteFiles {
  const files: SiteFiles = { appDir: config.v2.appDir, fontDirs: config.v2.fontDirs, rootDir: config.v2.rootDir };
  if (!existsSync(path.join(files.appDir, "index.html"))) {
    throw new Error(`Сборки v2 нет в ${files.appDir}: соберите frontend (npm run build) или поправьте v2 в parity.config.json`);
  }
  return files;
}

export function targetSite(name: TargetName, config: ParityConfig): SiteFiles {
  return name === "draft" ? draftSite(config) : v2Site(config);
}
