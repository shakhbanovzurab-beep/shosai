// Эталон: ключи хранилища не выходят за префикс, манифест сливается и чистится.

import { expect, test } from "@playwright/test";

import { mergeManifest, stateSnapshotSegments, wantedKey, type ManifestEntry } from "./manifest.ts";
import { BASELINE_PREFIX, objectKey } from "./store.ts";

const SHA = "a".repeat(64);

test("ключ снимка — внутри префикса стенда и только по хешу SHA-256", () => {
  expect(objectKey(SHA).startsWith(BASELINE_PREFIX)).toBe(true);
  expect(() => objectKey("../users/secret")).toThrow();
});

test("путь снимка — по сегментам идентификатора, без склейки точек", () => {
  expect(stateSnapshotSegments("auth.login.error-invalid")).toEqual(["auth", "login", "error-invalid.png"]);
});

test("манифест: снятое заменяет прежнее, пары не из реестра удаляются, порядок устойчив", () => {
  const entry = (cell: string, state: string, sha: string): ManifestEntry => ({ cell, state, sha256: sha, bytes: 1 });
  const previous = { draftCommit: "c", entries: [entry("b", "s", "1"), entry("a", "gone", "2"), entry("a", "s", "3")] };
  const wanted = new Set([wantedKey("a", "s"), wantedKey("b", "s")]);
  const merged = mergeManifest(previous, [entry("b", "s", "9")], wanted, "c");
  expect(merged.entries).toEqual([entry("a", "s", "3"), entry("b", "s", "9")]);
});
