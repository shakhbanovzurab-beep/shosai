import { apiRequest, jsonBody } from "@/lib/api-client";

import type {
  CheckoutRequest,
  CheckoutResponse,
  PlansResponse,
  SalesInquiryRequest,
  SalesInquiryResponse,
} from "../domain/contract";

const request = <T>(path: string, init?: RequestInit) => apiRequest<T>(`/api/billing${path}`, init);

export const upgradeApi = {
  plans: () => request<PlansResponse>("/plans"),
  checkout: (body: CheckoutRequest) => request<CheckoutResponse>("/checkout", jsonBody("POST", body)),
  salesInquiry: (body: SalesInquiryRequest) => request<SalesInquiryResponse>("/sales-inquiry", jsonBody("POST", body)),
};
