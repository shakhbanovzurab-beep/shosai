import { NextResponse } from "next/server";

import { z } from "zod";

import { forwardToBackend } from "@/server/backend-proxy";

import {
  COMPANY_MAX,
  MESSAGE_MAX,
  type PlansResponse,
  type SalesInquiryResponse,
  TEAM_SIZES,
} from "../domain/contract";
import { demoCurrentPlan, demoPlans, planCatalog, saveSalesInquiry } from "./demo-plans";
import { isProblem, refuse, refuseSeats } from "./problems";

const checkoutSchema = z.strictObject({ plan_id: z.string().min(1).max(40), seats: z.int().min(1).optional() });

// Messages are problem codes, worded for the request when it is refused (see ./problems).
const inquirySchema = z.strictObject({
  work_email: z.email("invalidEmail").max(254, "invalidEmail"),
  company: z.string().trim().min(1, "companyRequired").max(COMPANY_MAX),
  team_size: z.enum(TEAM_SIZES),
  message: z.string().trim().max(MESSAGE_MAX),
});

const readJson = (request: Request) => request.json().catch(() => null);

/** /api/billing/plans: the plans, the current one and this month's meeting minutes. */
export const plansRoute = {
  async GET(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/billing/plans");
    if (upstream) return upstream;
    return NextResponse.json<PlansResponse>(demoPlans());
  },
};

/** /api/billing/checkout: the payment provider's page for switching to a plan with a price. */
export const checkoutRoute = {
  async POST(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/billing/checkout");
    if (upstream) return upstream;
    const body = checkoutSchema.safeParse(await readJson(request));
    if (!body.success) return refuse("choosePlan", 422);
    const plans = planCatalog();
    const target = plans.find((p) => p.id === body.data.plan_id);
    if (!target) return refuse("planUnavailable", 404);
    if (!target.price) return refuse("salesOnly", 422);
    if (target.id === demoCurrentPlan(plans)?.id) return refuse("alreadyOnPlan", 409);
    const { seats } = body.data;
    if (target.seats) {
      const { min, max } = target.seats;
      if (seats === undefined || seats < min || (max !== null && seats > max)) return refuseSeats(min, max);
    } else if (seats !== undefined) return refuse("singleUser", 422);
    // The demo has no payment provider, so it says so instead of pretending; the backend answers with `{ url }`.
    return refuse("paymentsNotConnected", 501);
  },
};

/** /api/billing/sales-inquiry: an Enterprise request for the sales team. */
export const salesInquiryRoute = {
  async POST(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/billing/sales-inquiry");
    if (upstream) return upstream;
    const body = inquirySchema.safeParse(await readJson(request));
    if (!body.success) {
      const message = body.error.issues[0]?.message;
      return refuse(isProblem(message) ? message : "checkForm", 422);
    }
    saveSalesInquiry(body.data);
    return NextResponse.json<SalesInquiryResponse>({ status: "received" }, { status: 202 });
  },
};
