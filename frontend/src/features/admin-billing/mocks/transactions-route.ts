import { detail, JsonResponse } from "@/mocks/runtime";

import type { RefundResponse, TransactionsResponse } from "../domain/contract";
import { refundRequestSchema, transactionsQuerySchema } from "../domain/schemas";
import { renderInvoice } from "./invoice";
import { getTransaction, listTransactions, refundTransaction } from "./transactions";

type Context = { params: Promise<{ id: string }> };

/** `/api/admin/billing/transactions`: every customer payment, filtered and paged. */
export const transactionsRoute = {
  async GET(request: Request) {
    const { searchParams } = new URL(request.url);
    const query = transactionsQuerySchema.safeParse({
      status: searchParams.get("status") || undefined,
      period: searchParams.get("period") || undefined,
      currency: searchParams.get("currency") || undefined,
      page: searchParams.get("page") || undefined,
    });
    if (!query.success) return detail("Неверные параметры фильтра: status, period, currency или page.", 422);
    return JsonResponse.json<TransactionsResponse>(listTransactions(query.data));
  },
};

/** `/api/admin/billing/transactions/{id}/invoice`: the payment's invoice as a download. */
export const transactionInvoiceRoute = {
  async GET(_request: Request, { params }: Context) {
    const { id } = await params;
    const transaction = getTransaction(id);
    if (!transaction) return detail("Платёж не найден.", 404);
    if (!transaction.invoice_url) return detail("Счёт по этому платежу не выставлялся.", 404);
    return new Response(renderInvoice(transaction), {
      headers: {
        "content-type": "text/html; charset=utf-8",
        "content-disposition": `attachment; filename="${transaction.number}.html"`,
      },
    });
  },
};

/** `/api/admin/billing/transactions/{id}/refund`: a full or partial refund in the payment's currency. */
export const transactionRefundRoute = {
  async POST(request: Request, { params }: Context) {
    const { id } = await params;
    const body = refundRequestSchema.safeParse(await request.json().catch(() => null));
    if (!body.success) return detail(body.error.issues[0]?.message ?? "Отправьте { amount_minor }.", 422);
    const result = refundTransaction(id, body.data.amount_minor);
    return result.ok ? JsonResponse.json<RefundResponse>(result.transaction) : detail(result.message, result.status);
  },
};
