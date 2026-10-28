import { describe, expect, it } from "vitest";

import type { PlatformConfig } from "./contract";
import {
  BUILT_IN,
  cleaned,
  estimateTokens,
  layerText,
  nonLatinLetters,
  publishProblem,
  sameConfig,
} from "./platform-layer";

const config = (patch: Partial<PlatformConfig> = {}): PlatformConfig => ({ ...BUILT_IN, ...patch });
const rule = (id: string, text: string, enabled = true) => ({ id, text, enabled });

describe("слой платформы", () => {
  it("собирается так же, как на сервере: промт, правила по порядку, темы", () => {
    const draft = config({
      system_prompt: "  Answer plainly.  ",
      safety: {
        rules: [rule("a", "Cite your sources."), rule("b", "Off.", false), rule("c", "  ")],
        blocked_topics: [],
      },
    });

    expect(layerText(cleaned(draft))).toBe("Answer plainly.\n\nPlatform rules, in order:\n- Cite your sources.");
  });

  it("темы очищаются от повторов без учёта регистра и идут одной строкой", () => {
    const draft = config({ safety: { rules: [], blocked_topics: ["Gambling", " gambling ", "Crypto"] } });

    expect(layerText(cleaned(draft))).toBe(
      "Decline politely to discuss the following topics, and do not search the web for them: Gambling; Crypto.",
    );
  });

  it("токены считаются по байтам UTF-8, как у сервера", () => {
    expect(estimateTokens("abcdef")).toBe(2);
    expect(estimateTokens("абв")).toBe(2);
    expect(estimateTokens("")).toBe(0);
  });

  it("находит буквы не латиницей, а латиницу с диакритикой и знаки пропускает", () => {
    expect(nonLatinLetters("Café — 100 % ok")).toEqual([]);
    expect(nonLatinLetters("Отвечай кратко")).toEqual(["О", "а", "в", "е", "й", "к", "о", "р", "т", "ч"]);
  });
});

describe("что помешает публикации", () => {
  it("неанглийское включённое правило — с полем очищенной конфигурации", () => {
    const draft = config({
      safety: { rules: [rule("e", ""), rule("ru", "Отвечай кратко")], blocked_topics: [] },
    });

    expect(publishProblem(draft)).toEqual({ code: "platform_prompt_not_english", params: { field: "safety.rules.0" } });
  });

  it("выключенное правило модель не читает, поэтому оно не мешает", () => {
    const draft = config({ safety: { rules: [rule("ru", "Отвечай кратко", false)], blocked_topics: [] } });

    expect(publishProblem(draft)).toBeNull();
  });

  it("слой сверх бюджета и дополнение функции сверх своего", () => {
    const long = config({ system_prompt: "x".repeat(3_001) });
    const feature = config({
      features: { ...BUILT_IN.features, voice_mode: { content: "y".repeat(1_501), enabled: true } },
    });

    expect(publishProblem(long)).toEqual({
      code: "platform_layer_over_budget",
      params: { field: "layer", tokens: 1_001, max: 1_000 },
    });
    expect(publishProblem(feature)).toEqual({
      code: "platform_layer_over_budget",
      params: { field: "features.voice_mode", tokens: 501, max: 500 },
    });
  });
});

describe("сравнение с действующей версией", () => {
  it("пробелы по краям и пустые правила изменением не считаются", () => {
    const draft = config({ system_prompt: "Hi. ", safety: { rules: [rule("e", " ")], blocked_topics: [] } });

    expect(sameConfig(draft, config({ system_prompt: "Hi." }))).toBe(true);
    expect(sameConfig(draft, BUILT_IN)).toBe(false);
  });
});
