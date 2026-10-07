import { withFallback } from "./fallback";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

const english = { title: "Files", empty: { title: "No files yet", text: "Upload a file." } };

describe("withFallback", () => {
  it("prefers the translation", () => {
    const merged = withFallback(english, {
      title: "Файлы",
      empty: { title: "Файлов пока нет", text: "Загрузите файл." },
    });
    assert.deepEqual(merged, { title: "Файлы", empty: { title: "Файлов пока нет", text: "Загрузите файл." } });
  });

  it("keeps English for what the translation lacks or leaves blank", () => {
    const merged = withFallback(english, { title: " ", empty: { title: "Файлов пока нет" } });
    assert.deepEqual(merged, { title: "Files", empty: { title: "Файлов пока нет", text: "Upload a file." } });
  });

  it("drops keys English doesn't have and values of the wrong shape", () => {
    const merged = withFallback(english, { extra: "x", title: { nested: "x" }, empty: "x" });
    assert.deepEqual(merged, english);
  });
});
