import { JsonResponse } from "@/mocks/runtime";

import type { BillingOverview } from "../domain/contract";
import { getOverview } from "./overview";

/** `/api/admin/billing/overview`: KPIs, revenue, payment statuses and payouts per currency. */
export const billingOverviewRoute = {
  async GET(_request: Request) {
    return JsonResponse.json<BillingOverview>(getOverview());
  },
};
