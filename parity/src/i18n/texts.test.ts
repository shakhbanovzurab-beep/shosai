// texts.json содержит каждый ключ, на который ссылается код стенда, на каждом
// языке черновика: иначе маркер на этом языке упал бы уже при съёмке.

import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

import { PARITY_ROOT } from "../config.ts";
import { MATRIX_LANGUAGES, SWEEP_LANGUAGES } from "../matrix.ts";
import { TEXT_KEY_PATTERN, TEXTS_FILE, translator } from "./texts.ts";

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return sourceFiles(full);
    // Тесты стенда ключами интерфейса не пользуются; в них — проверочные ключи.
    return entry.name.endsWith(".ts") && !entry.name.endsWith(".test.ts") ? [full] : [];
  });
}

test("каждый ключ кода есть в texts.json на всех 16 языках", () => {
  const catalog = JSON.parse(readFileSync(TEXTS_FILE, "utf8")) as Record<string, Record<string, string>>;
  const missing: string[] = [];
  for (const file of sourceFiles(path.join(PARITY_ROOT, "src"))) {
    for (const match of readFileSync(file, "utf8").matchAll(TEXT_KEY_PATTERN)) {
      const key = match[1] ?? "";
      for (const language of [...MATRIX_LANGUAGES, ...SWEEP_LANGUAGES]) {
        if (catalog[language]?.[key] === undefined) missing.push(`${language} ${key}`);
      }
    }
  }
  expect(missing).toEqual([]);
});

test("подстановка переменных и отказ на неизвестном ключе", () => {
  const t = translator("ru", { ru: { "ns:greet": "Шаг {{current}} из {{total}}" } });
  expect(t("ns:greet", { current: 1, total: 24 })).toBe("Шаг 1 из 24");
  expect(() => t("ns:missing")).toThrow();
});
