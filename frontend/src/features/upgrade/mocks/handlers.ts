// Моки разработки слайса, по записи на путь. Планы — на пути бэкенда `/v1` (billing, шаг 6); оплата и заявка
// в продажи — учебные `/api/billing/*`, пока платёжные шаги billing не опубликуют их (F2-D1).
import { type MockRoute, mockRoute } from "@/mocks/routing";

import { checkoutRoute, plansRoute, salesInquiryRoute } from "./billing-route";

export const handlers: MockRoute[] = [
  mockRoute("/api/billing/checkout", checkoutRoute, ["POST"]),
  mockRoute("/v1/billing/plans", plansRoute, ["GET"]),
  mockRoute("/api/billing/sales-inquiry", salesInquiryRoute, ["POST"]),
];
