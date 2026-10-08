import { apiRequest, jsonBody } from "@/lib/api/request";

import type { BillingOverview, RefundRequest, RefundResponse, TransactionsResponse } from "../domain/contract";

const BASE = "/api/admin/billing";

export const billingApi = {
  overview: () => apiRequest<BillingOverview>(`${BASE}/overview`),
  /** `search` is the query string from `transactionsSearch`, "" or "?status=…". */
  transactions: (search: string) => apiRequest<TransactionsResponse>(`${BASE}/transactions${search}`),
  refund: (id: string, body: RefundRequest) =>
    apiRequest<RefundResponse>(`${BASE}/transactions/${encodeURIComponent(id)}/refund`, jsonBody("POST", body)),
};
