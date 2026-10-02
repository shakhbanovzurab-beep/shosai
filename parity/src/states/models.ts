// Модели (шаг 5): назначения по ролям и каталог; раздел администратора —
// баланс OpenRouter, расходы, реестр, каталог и дефолты. Раздел администратора
// черновик пишет без переводов: его тексты в селекторах — как на экране.

import type { Page } from "@playwright/test";

import type { JsonValue } from "../fixtures/format.ts";
import { exactText, type Translate } from "../i18n/texts.ts";
import { merged } from "./admin-dashboard.ts";
import { hold, reply, serverError } from "./overrides.ts";
import type { State } from "./types.ts";

const PREVIEW = "/v1/admin/models/registry/preview";
const DEFAULTS = "/v1/admin/models/model-defaults";
const RETIRED_MODEL = "openai/gpt-4o-2024-05-13";
const OPENROUTER = "спеки и баланс приходят из API OpenRouter; у стенда нет ключа и сети";

function models(id: string, marker: (t: Translate) => string, extra: Partial<State> = {}): State {
  return { id: `models.${id}`, fixture: "models/page", scope: "single", marker, ...extra };
}

function admin(id: string, marker: () => string, extra: Partial<State> = {}): State {
  return { id: `admin-models.${id}`, fixture: "admin/ai-models", scope: "single", marker, ...extra };
}

/** Выбор модели роли «Код»: засеянное назначение — DeepSeek V4 Pro, единственное на экране. */
async function openCodingSelect(page: Page): Promise<void> {
  await page.getByRole("button", { name: "DeepSeek • Deepseek V4 Pro", exact: true }).click();
}

async function previewTicker(page: Page): Promise<void> {
  await page.getByLabel("Тикер модели (provider/model)", { exact: true }).fill("anthropic/claude-opus-4.5");
  await page.getByRole("button", { name: "Получить спеки", exact: true }).click();
}

const preview = (priceKnown: boolean): { [key: string]: JsonValue } => ({
  openrouter_model_id: "anthropic/claude-opus-4.5",
  provider: "anthropic",
  display: "Anthropic • Claude Opus 4.5",
  model_type: "chat",
  pricing_input: priceKnown ? "0.005" : "0",
  pricing_output: priceKnown ? "0.025" : "0",
  context_window: 200_000,
  capabilities: ["CHAT", "STREAMING", "VISION", "REASONING", "LONG CONTEXT"],
  description: "Frontier model for complex reasoning and coding.",
  price_known: priceKnown,
});

const role = (name: string, model: string, type = "chat"): { [key: string]: JsonValue } => ({
  role: name,
  model_id: model,
  model_type: type,
  temperature: 0.7,
  max_tokens: 4096,
  reasoning: false,
});

/** Роль «Скриншоты» после правки: температура засева 0.7 сдвинута на шаг ползунка. */
const WARMER_VISION = { ...role("vision", "google/gemini-3-flash-preview"), temperature: 0.8 };
const ROLE_SAVED = "правка роли меняет данные засева; после сохранения черновик перечитывает назначения";
const SAVED_ROLES: JsonValue = [
  role("responses", "anthropic/claude-haiku-4.5"),
  { ...role("coding", "deepseek/deepseek-v4-pro"), temperature: 0.2, max_tokens: 8192 },
  WARMER_VISION,
  role("system_design", "anthropic/claude-haiku-4.5"),
  role("generation", "deepseek/deepseek-v4-flash"),
  role("transcription", "openai/gpt-4o-mini-transcribe", "transcription"),
  { ...role("agent", "deepseek/deepseek-v4-flash"), reasoning: null },
];

/**
 * Назначения, которые показывают особые строки роли: модель с выбором
 * рассуждения, «Скриншоты» на модели без зрения, модель без температуры и без
 * рассуждения.
 */
const VARIANT_ROLES = [
  role("responses", "mistralai/mistral-large-3"),
  role("coding", "deepseek/deepseek-v4-pro"),
  role("vision", "deepseek/deepseek-v4-flash"),
  role("system_design", "openai/gpt-5.4-mini"),
  role("generation", "perplexity/sonar"),
  role("transcription", "openai/gpt-4o-mini-transcribe", "transcription"),
  { ...role("agent", "deepseek/deepseek-v4-flash"), reasoning: null },
];

export const MODELS_STATES: readonly State[] = [
  models("populated", (t) => exactText(t("models:models.catalogTitle")), { scope: "full" }),
  models("loading", () => "svg.spin", { overrides: [hold("GET", "/v1/me/models/configs")] }),
  models("role.select-open", () => '[role=option]:has-text("DeepSeek • Deepseek V4 Pro")', { act: openCodingSelect }),
  models("role.saving", (t) => exactText(t("models:models.savingShort")), {
    overrides: [hold("PUT", "/v1/me/models/roles/{role}")],
    act: async (page) => {
      await openCodingSelect(page);
      await page.getByRole("option", { name: "Alibaba • Qwen3 Coder", exact: true }).click();
    },
  }),
  // «✓» есть и в колонке «Вкл.» каталога; у роли это ячейка статуса сохранения.
  // Смена модели пересоздаёт строку (ключ — модель), и «✓» пропадает; держится
  // он после правки температуры или лимита токенов.
  models("role.saved", () => 'div.upper.text-end:text-is("✓")', {
    overrides: [
      reply("PUT", "/v1/me/models/roles/{role}", 200, WARMER_VISION, ROLE_SAVED),
      { method: "GET", path: "/v1/me/models/roles", reason: ROLE_SAVED, respond: ["recorded", { status: 200, body: SAVED_ROLES }] },
    ],
    act: async (page, { t }) => {
      // Ползунки температуры идут по порядку ролей: «Ответы в эфире», затем «Скриншоты».
      await page.getByLabel(t("models:models.temperature"), { exact: true }).nth(1).focus();
      await page.keyboard.press("ArrowRight");
    },
  }),
  models("role.variants", (t) => `[role=switch][aria-label=${JSON.stringify(t("models:models.reasoningLabel", { role: t("common:roles.responses") }))}]`, {
    overrides: [reply("GET", "/v1/me/models/roles", 200, VARIANT_ROLES, "засеяны обычные назначения; особые строки роли — у других моделей")],
  }),
  models("catalog.row-expanded", (t) => exactText(t("models:models.axis.value")), {
    act: async (page, { t }) =>
      page.locator(`button[aria-label=${JSON.stringify(t("models:models.blurbLabel", { model: "Mistral • Large 3" }))}]`).click(),
  }),

  admin("populated", () => 'text="Баланс (остаток)"', {
    scope: "full",
    // Тексты раздела вшиты по-русски (находка в инвентаре): на en v2 покажет перевод.
    languages: ["ru"],
    overrides: [reply("GET", "/v1/admin/models/balance", 200,
      { total_credits: 50, total_usage: 12.3, balance: 37.7, currency: "USD" }, OPENROUTER)],
  }),
  admin("balance.error", () => 'text="Баланс OpenRouter недоступен."'),
  admin("balance.loading", () => "svg.spin", { overrides: [hold("GET", "/v1/admin/models/balance")] }),
  admin("balance.ok", () => 'text="Пополнено"', {
    overrides: [reply("GET", "/v1/admin/models/balance", 200, { total_credits: 250, total_usage: 87.4321, balance: 162.5679, currency: "USD" }, OPENROUTER)],
  }),
  admin("usage.empty", () => 'text="Расходов по моделям пока нет."', {
    overrides: [reply("GET", "/v1/admin/models/usage", 200, [], "у засеянной персоны есть расходы на модели")],
  }),
  admin("registry.empty", () => 'text="Реестр пуст — импортируйте модель выше."', {
    reveal: true,
    overrides: [reply("GET", "/v1/admin/models/registry", 200, [], "миграции черновика переносят встроенные модели в реестр")],
  }),
  admin("catalog", () => 'text="Каталог моделей"', { reveal: true }),
  admin("defaults", () => 'text="Дефолты моделей"', { reveal: true }),
  admin("defaults.loading", () => "svg.spin", { reveal: true, overrides: [hold("GET", DEFAULTS)] }),
  admin("defaults.error", () => 'text="Не удалось сохранить. Проверьте выбор моделей."', {
    reveal: true,
    overrides: [serverError("PUT", DEFAULTS)],
    act: async (page) => page.getByRole("button", { name: "Сохранить дефолты", exact: true }).click(),
  }),
  admin("defaults.stale-cell", () => `text="${RETIRED_MODEL} (вне каталога)"`, {
    reveal: true,
    overrides: [merged("GET", DEFAULTS, { agent_model_id: RETIRED_MODEL },
      "модель агента сняли с каталога после назначения; засев назначает только модели каталога")],
  }),
  admin("defaults.saving", () => 'button:disabled:has-text("Сохранение…")', {
    reveal: true,
    overrides: [hold("PUT", DEFAULTS)],
    act: async (page) => page.getByRole("button", { name: "Сохранить дефолты", exact: true }).click(),
  }),
  admin("import.preview", () => 'button:has-text("Добавить в реестр")', {
    reveal: true,
    overrides: [reply("GET", PREVIEW, 200, preview(true), OPENROUTER)],
    act: previewTicker,
  }),
  admin("import.price-unknown", () => 'text="цена не задана — введите вручную"', {
    reveal: true,
    overrides: [reply("GET", PREVIEW, 200, preview(false), OPENROUTER)],
    act: previewTicker,
  }),
  admin("import.error", () => 'text="Не удалось получить спеки: проверьте тикер и доступность OpenRouter."', {
    reveal: true,
    overrides: [reply("GET", PREVIEW, 502, { detail: "openrouter_unavailable" }, OPENROUTER)],
    act: previewTicker,
  }),
  admin("registry.dirty-price", () => 'button:has-text("Сохранить цену")', {
    reveal: true,
    act: async (page) => page.getByLabel("Цена вход Mistral • Large 3", { exact: true }).fill("0.0006"),
  }),
  admin("registry.delete-confirm", () => 'dialog[aria-label="Удалить модель"]', {
    act: async (page) => page.getByRole("button", { name: "Удалить Mistral • Large 3 из реестра", exact: true }).first().click(),
  }),
  {
    // Раздел только для администратора: пользователя черновик возвращает домой.
    id: "admin-models.redirect",
    fixture: "leo/home",
    url: "/app/admin/ai-models",
    scope: "single",
    marker: (t) => exactText(t("analytics:analytics.description")),
  },
];
