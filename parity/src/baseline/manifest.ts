// Манифест эталона: какие снимки черновика считаются эталоном. В git лежит только
// он (baseline/manifest.json); сами снимки — в S3 по ключу из хеша содержимого
// и в локальной копии .cache/baseline/<ячейка>/<путь состояния>.png.

import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

import { PARITY_ROOT } from "../config.ts";

export const MANIFEST_FILE = path.join(PARITY_ROOT, "baseline", "manifest.json");
export const LOCAL_BASELINE_DIR = path.join(PARITY_ROOT, ".cache", "baseline");

export interface ManifestEntry {
  readonly cell: string;
  readonly state: string;
  readonly sha256: string;
  readonly bytes: number;
}

export interface Manifest {
  /** Коммит черновика, с которого снят эталон. */
  readonly draftCommit: string;
  readonly entries: readonly ManifestEntry[];
}

/** Путь снимка состояния внутри ячейки: `auth.login.default` → auth/login/default.png. */
export function stateSnapshotSegments(stateId: string): string[] {
  const segments = stateId.split(".");
  const last = segments.pop() ?? stateId;
  return [...segments, `${last}.png`];
}

export function localSnapshot(cell: string, stateId: string): string {
  return path.join(LOCAL_BASELINE_DIR, cell, ...stateSnapshotSegments(stateId));
}

export function sha256(bytes: Buffer): string {
  return createHash("sha256").update(bytes).digest("hex");
}

export function readManifest(draftCommit: string): Manifest {
  if (!existsSync(MANIFEST_FILE)) return { draftCommit, entries: [] };
  return JSON.parse(readFileSync(MANIFEST_FILE, "utf8")) as Manifest;
}

function entryKey(entry: Pick<ManifestEntry, "cell" | "state">): string {
  return `${entry.cell} ${entry.state}`;
}

/**
 * Новый манифест: прежние записи, обновлённые снятыми сейчас, без пар
 * «ячейка — состояние», которых больше нет в реестре.
 */
export function mergeManifest(
  previous: Manifest,
  captured: readonly ManifestEntry[],
  wanted: ReadonlySet<string>,
  draftCommit: string,
): Manifest {
  const entries = new Map<string, ManifestEntry>();
  for (const entry of previous.entries) entries.set(entryKey(entry), entry);
  for (const entry of captured) entries.set(entryKey(entry), entry);
  const kept = [...entries.values()].filter((entry) => wanted.has(entryKey(entry)));
  kept.sort((a, b) => entryKey(a).localeCompare(entryKey(b)));
  return { draftCommit, entries: kept };
}

export function wantedKey(cell: string, state: string): string {
  return entryKey({ cell, state });
}

export function writeManifest(manifest: Manifest): void {
  mkdirSync(path.dirname(MANIFEST_FILE), { recursive: true });
  writeFileSync(MANIFEST_FILE, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
}
