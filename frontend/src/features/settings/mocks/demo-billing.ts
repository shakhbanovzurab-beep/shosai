import { demoCurrentPlan, planCatalog } from "@/features/upgrade/mocks/demo-plans";

import type { Billing, Invoice, Usage } from "../domain/billing-contract";

/* Fixed billing and usage samples for the demo, used when BACKEND_API_URL is unset. */

/** First day of the month `back` months ago, UTC — demo invoices fall on the 1st. */
const monthStart = (back: number) => {
  const now = new Date();
  return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - back, 1));
};

/** What the payment provider wrote on each invoice: it stays as written in every interface language. */
const INVOICE_LINE = "Professional plan · monthly";

const demoInvoice = (back: number, status: Invoice["status"]): Invoice => {
  const date = monthStart(back);
  const number = `INV-${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(3, "0")}`;
  return {
    id: number.toLowerCase(),
    number,
    date: date.toISOString(),
    description: INVOICE_LINE,
    amount_cents: planCatalog().find((p) => p.id === "professional")?.price?.amount_cents ?? 0,
    currency: "USD",
    status,
    download_url: `/api/settings/billing/invoices/${number.toLowerCase()}`,
  };
};

export function demoBilling(): Billing {
  // The demo user is on Basic (free) after a few paid months of Professional, as on the Upgrade page.
  const current = demoCurrentPlan();
  const price = current?.price?.amount_cents ?? 0;
  return {
    plan: {
      id: current?.id ?? "basic",
      name: current?.name ?? "Basic",
      price_cents: price,
      currency: "USD",
      interval: price > 0 ? "month" : null,
    },
    renews_at: price > 0 ? monthStart(-1).toISOString() : null,
    payment_methods: [
      { id: "pm_demo", brand: "mastercard", last4: "1285", exp_month: 12, exp_year: 2030, is_default: true },
    ],
    invoices: [
      demoInvoice(1, "paid"),
      demoInvoice(2, "paid"),
      demoInvoice(3, "paid"),
      demoInvoice(4, "failed"),
      demoInvoice(5, "paid"),
    ],
  };
}

/** This week runs Monday 00:00 UTC to the next Monday. */
function currentWeek() {
  const now = new Date();
  const daysSinceMonday = (now.getUTCDay() + 6) % 7;
  const start = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() - daysSinceMonday));
  return { start, end: new Date(start.getTime() + 7 * 86400000) };
}

export function demoUsage(): Usage {
  const { start, end } = currentWeek();
  return {
    week_start: start.toISOString(),
    resets_at: end.toISOString(),
    limits: [
      { tier: "standard", used_tokens: 3_420_000, limit_tokens: 10_000_000 },
      { tier: "frontier", used_tokens: 860_000, limit_tokens: 1_000_000 },
    ],
    frontier: {
      extra_tokens: 1_250_000,
      models: [
        { model_id: "claude-opus-5-5", provider: "Anthropic", name: "Claude Opus 5.5", used_tokens: 512_000 },
        { model_id: "gpt-astra", provider: "OpenAI", name: "GPT Astra", used_tokens: 228_000 },
        { model_id: "claude-fable-5-1", provider: "Anthropic", name: "Claude Fable 5.1", used_tokens: 120_000 },
      ],
      packs: [
        { id: "frontier_1m", tokens: 1_000_000, price_cents: 1500, currency: "USD" },
        { id: "frontier_5m", tokens: 5_000_000, price_cents: 6500, currency: "USD" },
        { id: "frontier_20m", tokens: 20_000_000, price_cents: 22000, currency: "USD" },
      ],
    },
  };
}
