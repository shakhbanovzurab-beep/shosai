import { describe, expect, it } from "vitest";

import { shownTitle } from "./report-titles";

const report = (id: string) => ({ kind: "report" as const, id, title: "Server title" });

describe("shownTitle", () => {
  it("names the platform's reports in Russian by their ids", () => {
    expect(shownTitle(report("spend.summary:month:model"))).toBe("Расходы на ИИ, этот месяц, по моделям");
    expect(shownTitle(report("spend.daily:14"))).toBe("Расходы на ИИ по дням, 14 дн.");
    expect(shownTitle(report("spend.forecast"))).toBe("Прогноз расходов на ИИ на этот месяц");
    expect(shownTitle(report("openrouter.balance"))).toBe("Баланс OpenRouter");
    expect(shownTitle(report("ratings:30"))).toBe("Оценки ответов Leo, 30 дн.");
    expect(shownTitle(report("billing.plans"))).toBe("Тарифы и подписчики");
    expect(shownTitle(report("billing.promo_codes"))).toBe("Промокоды");
    expect(shownTitle(report("identity.accounts:7"))).toBe("Аккаунты по домам данных, 7 дн.");
  });

  it("keeps the server's title for an unknown report and for other sources", () => {
    expect(shownTitle(report("spend.summary:decade:model"))).toBe("Server title");
    expect(shownTitle(report("spend.daily"))).toBe("Server title");
    expect(shownTitle(report("traffic.weekly"))).toBe("Server title");
    expect(shownTitle({ kind: "meeting", id: "spend.daily:14", title: "Budget review" })).toBe("Budget review");
  });
});
