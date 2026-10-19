import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";
import { apiRequest, jsonBody } from "@/lib/api/request";

import type {
  CheckoutRequest,
  CheckoutResponse,
  PlansResponse,
  SalesInquiryRequest,
  SalesInquiryResponse,
} from "../domain/contract";

// Оплата ждёт платёжные шаги billing (8–11): до них оплата и заявка в продажи идут на учебные маршруты моков.
const sample = <T>(path: string, init?: RequestInit) => apiRequest<T>(`/api/billing${path}`, init);

export const upgradeApi = {
  /** The plans in the account's currency, the person's own and effective plan, and the month's minutes. */
  plans: (): Promise<PlansResponse> => dataOf(apiClient.GET("/v1/billing/plans")),
  checkout: (body: CheckoutRequest) => sample<CheckoutResponse>("/checkout", jsonBody("POST", body)),
  salesInquiry: (body: SalesInquiryRequest) => sample<SalesInquiryResponse>("/sales-inquiry", jsonBody("POST", body)),
};
