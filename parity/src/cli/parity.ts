// Команды стенда сравнения (запускаются в контейнере через scripts/parity.sh):
//
//   baseline [аргументы Playwright] — снять черновик, выгрузить новые снимки в S3,
//                                     обновить baseline/manifest.json;
//   verify   [аргументы]            — снять черновик и сравнить с эталоном без допуска;
//   compare  [аргументы]            — снять v2 и сравнить с эталоном с допуском паритета.
//
// Аргументы Playwright выбирают подмножество: `--grep "billing\."`.

import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

import {
  localSnapshot,
  mergeManifest,
  readManifest,
  sha256,
  wantedKey,
  writeManifest,
  type ManifestEntry,
} from "../baseline/manifest.ts";
import { objectKey, s3StoreFromEnv, type BaselineStore } from "../baseline/store.ts";
import { loadParityConfig, PARITY_ROOT } from "../config.ts";
import { parseMode, type Mode } from "../harness/mode.ts";
import { ALL_STATES, stateCells } from "../states/registry.ts";

const REPORT_FILE = path.join(PARITY_ROOT, ".cache", "results.json");

interface ReportTest {
  readonly projectName: string;
  readonly status: string;
}
interface ReportSpec {
  readonly title: string;
  readonly tests: readonly ReportTest[];
}
interface ReportSuite {
  readonly specs?: readonly ReportSpec[];
  readonly suites?: readonly ReportSuite[];
}

function runPlaywright(mode: Mode, args: readonly string[]): number {
  const target = mode === "compare" ? "v2" : "draft";
  const update = mode === "baseline" ? "all" : "none";
  const result = spawnSync("npx", ["playwright", "test", `--update-snapshots=${update}`, ...args], {
    cwd: PARITY_ROOT,
    stdio: "inherit",
    env: { ...process.env, PARITY_TARGET: target, PARITY_MODE: mode },
  });
  if (result.error !== undefined) throw result.error;
  return result.status ?? 1;
}

/** Пары «ячейка — состояние», снятые успешно, по JSON-отчёту Playwright. */
function capturedPairs(): Array<{ cell: string; state: string }> {
  const report = JSON.parse(readFileSync(REPORT_FILE, "utf8")) as ReportSuite;
  const pairs: Array<{ cell: string; state: string }> = [];
  const walk = (suite: ReportSuite): void => {
    for (const spec of suite.specs ?? []) {
      for (const test of spec.tests) {
        if (test.status === "expected") pairs.push({ cell: test.projectName, state: spec.title });
      }
    }
    for (const child of suite.suites ?? []) walk(child);
  };
  walk(report);
  return pairs;
}

async function publishBaseline(store: BaselineStore, draftCommit: string): Promise<void> {
  const captured: ManifestEntry[] = [];
  let uploaded = 0;
  for (const { cell, state } of capturedPairs()) {
    const bytes = readFileSync(localSnapshot(cell, state));
    const digest = sha256(bytes);
    const key = objectKey(digest);
    if (!(await store.exists(key))) {
      await store.put(key, bytes);
      uploaded += 1;
    }
    captured.push({ cell, state, sha256: digest, bytes: bytes.length });
  }
  const wanted = new Set(ALL_STATES.flatMap((state) => stateCells(state).map((cell) => wantedKey(cell.name, state.id))));
  writeManifest(mergeManifest(readManifest(draftCommit), captured, wanted, draftCommit));
  console.info(`Эталон: снято ${captured.length}, выгружено новых ${uploaded}, манифест обновлён`);
}

/** Локальная копия эталона по манифесту: недостающее и несовпавшее — из S3. */
async function restoreBaseline(draftCommit: string): Promise<void> {
  const manifest = readManifest(draftCommit);
  if (manifest.draftCommit !== draftCommit) {
    throw new Error(`Эталон снят с коммита ${manifest.draftCommit}, а закреплён ${draftCommit}: снимите эталон заново`);
  }
  let store: BaselineStore | null = null;
  let downloaded = 0;
  for (const entry of manifest.entries) {
    const file = localSnapshot(entry.cell, entry.state);
    if (existsSync(file) && sha256(readFileSync(file)) === entry.sha256) continue;
    store ??= s3StoreFromEnv();
    const bytes = await store.get(objectKey(entry.sha256));
    if (sha256(bytes) !== entry.sha256) throw new Error(`Снимок ${entry.cell} ${entry.state} в S3 не совпал с манифестом`);
    mkdirSync(path.dirname(file), { recursive: true });
    writeFileSync(file, bytes);
    downloaded += 1;
  }
  console.info(`Эталон: в манифесте ${manifest.entries.length}, загружено из S3 ${downloaded}`);
}

async function main(): Promise<number> {
  const [command, ...args] = process.argv.slice(2);
  const mode = parseMode(command);
  const { draftCommit } = loadParityConfig();
  if (mode === "baseline") {
    // Хранилище проверяется до съёмки: снимки без выгрузки были бы эталоном одной машины.
    const store = s3StoreFromEnv();
    const status = runPlaywright(mode, args);
    if (status !== 0) return status;
    await publishBaseline(store, draftCommit);
    return 0;
  }
  await restoreBaseline(draftCommit);
  return runPlaywright(mode, args);
}

process.exitCode = await main();
