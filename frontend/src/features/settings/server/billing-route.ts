import { NextResponse } from "next/server";

import { getFormatter, getTranslations } from "next-intl/server";
import { z } from "zod";

import { forwardToBackend } from "@/server/backend-proxy";

import type { Billing, Invoice, Usage } from "../domain/billing-contract";
import { demoBilling, demoUsage } from "./demo-billing";
import { readJson, refuse } from "./problems";

/** /api/settings/billing */
export const billingRoute = {
  async GET(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/settings/billing");
    if (upstream) return upstream;
    return NextResponse.json<Billing>(demoBilling());
  },
};

/** /api/settings/billing/portal */
export const billingPortalRoute = {
  /**
   * Returns the payment provider's hosted page for adding or updating a card. The demo has no
   * provider, so it says so instead of pretending; the backend answers with `{ url }`.
   */
  async POST(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/settings/billing/portal");
    if (upstream) return upstream;
    return refuse("paymentsUnavailable", 501);
  },
};

/** The demo's plain-text stand-in for an invoice PDF, in the request's interface language. */
async function demoInvoiceText(invoice: Invoice) {
  const [t, billing, format] = await Promise.all([
    getTranslations("settingsApi"),
    getTranslations("settingsBilling"),
    getFormatter(),
  ]);
  return [
    t("invoice.title", { number: invoice.number }),
    // Invoices are dated by calendar day in UTC, the time zone next-intl formats in.
    t("invoice.date", { date: format.dateTime(new Date(invoice.date), "medium") }),
    t("invoice.description", { description: invoice.description }),
    t("invoice.amount", {
      amount: format.number(invoice.amount_cents / 100, { style: "currency", currency: invoice.currency }),
    }),
    t("invoice.status", { status: billing(`history.status.${invoice.status}`) }),
    "",
    t("invoice.demoNote"),
  ].join("\n");
}

/** /api/settings/billing/invoices/[id] */
export const invoiceRoute = {
  /** Downloads one invoice. The backend serves the PDF; the demo writes a plain-text stand-in. */
  async GET(request: Request, { params }: { params: Promise<{ id: string }> }) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, `/v1/settings/billing/invoices/${encodeURIComponent(id)}`);
    if (upstream) return upstream;
    const invoice = demoBilling().invoices.find((i) => i.id === id);
    if (!invoice) return refuse("invoiceNotFound", 404);
    return new Response(await demoInvoiceText(invoice), {
      headers: {
        "content-type": "text/plain; charset=utf-8",
        "content-disposition": `attachment; filename="${invoice.number}.txt"`,
      },
    });
  },
};

/** /api/settings/usage */
export const usageRoute = {
  async GET(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/settings/usage");
    if (upstream) return upstream;
    return NextResponse.json<Usage>(demoUsage());
  },
};

/** /api/settings/usage/top-up */
export const topUpRoute = {
  /**
   * Starts buying a pack of extra frontier-model tokens; the backend answers `{ url }` with the
   * payment provider's checkout. The demo has no provider, so it says so instead of pretending.
   */
  async POST(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/settings/usage/top-up");
    if (upstream) return upstream;
    const body = z.object({ pack_id: z.string().min(1).max(100) }).safeParse(await readJson(request));
    if (!body.success) return refuse("invalidRequest", 422);
    return refuse("checkoutUnavailable", 501);
  },
};
