import type { CardBrand } from "@/lib/card-brand";

/* Billing and usage part of the settings API contract (see settings-contract.ts). */

/* ---------- Billing: GET /settings/billing ---------- */

export type InvoiceStatus = "paid" | "pending" | "failed";

export type Invoice = {
  id: string;
  /** Human-facing number, e.g. "INV-2026-010". */
  number: string;
  date: string;
  description: string;
  amount_cents: number;
  currency: string;
  status: InvoiceStatus;
  /** Where to download the PDF; null until it has been issued. */
  download_url: string | null;
};

/** A saved card. Card details are entered on the payment provider's page, never in our UI. */
export type PaymentMethod = {
  id: string;
  brand: CardBrand;
  last4: string;
  exp_month: number;
  exp_year: number;
  /** Charged for renewals, extra usage and auto-reload. Exactly one method is the default. */
  is_default: boolean;
};

export type Billing = {
  plan: { id: string; name: string; price_cents: number; currency: string; interval: "month" | "year" | null };
  renews_at: string | null;
  payment_methods: PaymentMethod[];
  invoices: Invoice[];
};

/* ---------- POST /settings/billing/portal ---------- */

/** Asks for the payment provider's hosted page (e.g. a Stripe customer portal or setup session). */
export type BillingPortalRequest =
  | { intent: "add_payment_method" }
  | { intent: "update_payment_method"; payment_method_id: string };
export type BillingPortalResponse = { url: string };

/* ---------- Usage: GET /settings/usage, POST /settings/usage/top-up ---------- */

/**
 * Standard models only have a weekly allowance. Frontier models (the expensive ones — Claude Opus,
 * GPT Astra and the like) have one too, and extra tokens can be bought for them; nothing else can.
 */
export type ModelTier = "standard" | "frontier";

/** Tokens included in the plan for one tier this week. */
export type WeeklyLimit = { tier: ModelTier; used_tokens: number; limit_tokens: number };

export type FrontierModelUsage = { model_id: string; provider: string; name: string; used_tokens: number };

/** A one-off bundle of extra frontier tokens. Purchased tokens don't reset weekly. */
export type TokenPack = { id: string; tokens: number; price_cents: number; currency: string };

export type Usage = {
  week_start: string;
  /** When the weekly allowances reset. */
  resets_at: string;
  limits: WeeklyLimit[];
  frontier: {
    /** Purchased tokens left; spent only after this week's frontier allowance runs out. */
    extra_tokens: number;
    /** This week, most used first. */
    models: FrontierModelUsage[];
    packs: TokenPack[];
  };
};

/** Returns the payment provider's checkout page for the pack. */
export type TopUpRequest = { pack_id: string };
export type TopUpResponse = { url: string };
