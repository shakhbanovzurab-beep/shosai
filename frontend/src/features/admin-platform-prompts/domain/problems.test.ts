import { describe, expect, it } from "vitest";

import type { PlatformConfig } from "./contract";
import { BUILT_IN } from "./platform-layer";
import { problemText } from "./problems";

const draft: PlatformConfig = {
  ...BUILT_IN,
  safety: {
    rules: [
      { id: "empty", text: " ", enabled: true },
      { id: "ru", text: "Отвечай кратко", enabled: true },
    ],
    blocked_topics: ["Казино"],
  },
};

describe("слова ошибок студии", () => {
  it("номер правила — тот, что видит админ, а не индекс очищенной конфигурации", () => {
    const text = problemText({ code: "platform_prompt_not_english", params: { field: "safety.rules.0" } }, draft);

    expect(text).toBe("Модель читает только английский текст — перепишите по-английски правило 2.");
  });

  it("тема называется по тексту, функция — по названию", () => {
    const topic = problemText(
      { code: "platform_prompt_not_english", params: { field: "safety.blocked_topics.0" } },
      draft,
    );
    const feature = problemText(
      { code: "platform_layer_over_budget", params: { field: "features.voice_mode", tokens: 1200, max: 500 } },
      draft,
    );

    expect(topic).toContain("тему «Казино»");
    expect(feature).toMatch(/^Промт функции «Голосовой режим» — ≈1\s200 токенов при лимите 500\. Сократите текст\.$/);
  });

  it("неизвестный код оставляет слова общему описанию", () => {
    expect(problemText({ code: "nothing_to_publish", params: {} }, draft)).toContain("публиковать нечего");
    expect(problemText({ code: "surprise", params: {} }, draft)).toBeNull();
  });
});
