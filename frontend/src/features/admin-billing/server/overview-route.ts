import { NextResponse } from "next/server";

import { forwardToBackend } from "@/server/backend-proxy";

import type { BillingOverview } from "../domain/contract";
import { getOverview } from "./overview";

/** `/api/admin/billing/overview`: KPIs, revenue, payment statuses and payouts per currency. */
export const billingOverviewRoute = {
  async GET(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/admin/billing/overview");
    if (upstream) return upstream;
    return NextResponse.json<BillingOverview>(getOverview());
  },
};
