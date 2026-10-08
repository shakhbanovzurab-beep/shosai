import { createTranslator } from "use-intl";
import { describe, it } from "vitest";

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";

// The Hub's Russian wording comes from its specification, which keeps number phrases in one form ("4 дн.").
const ru = JSON.parse(readFileSync(join(import.meta.dirname, "../../i18n/messages/ru/hub.json"), "utf8"));
// Read as plain data, so keys are strings here rather than the app's typed keys.
const t = createTranslator({ locale: "ru", messages: { hub: ru }, namespace: "hub" }) as unknown as (
  key: string,
  values: Record<string, number>,
) => string;

describe("Hub wording in Russian", () => {
  const phrases: Record<string, [number, string]> = {
    contradiction: [12, "решение изменилось 12 дн. назад"],
    overdue: [4, "просрочено на 4 дн."],
    due_soon: [2, "срок через 2 дн."],
    forgotten: [15, "обещано, и ни слова 15 дн."],
    undated: [17, "обещано без срока, 17 дн."],
    orphan_decision: [9, "решено 9 дн. назад, работа не начата"],
    unanswered: [3, "без ответа 3 дн."],
    silence: [23, "по делу нет разговоров 23 дн."],
  };
  for (const [kind, [days, text]] of Object.entries(phrases))
    it(`words ${kind} as the specification does`, () => {
      assert.equal(t(`gap.${kind}`, { days }), text);
    });

  it("says today for a gap of zero days", () => {
    assert.equal(t("gap.due_soon", { days: 0 }), "срок сегодня");
  });
});
