"use client";

import { toast } from "sonner";

import { errorMessage } from "@/lib/errors";

import { upgradeApi } from "../api/upgrade-api";
import type { CheckoutRequest, SalesInquiryRequest } from "../domain/contract";

/*
 * The server words its refusals in the interface language, so they are shown as they come; the caller
 * passes the words for a failure the server didn't explain.
 */

/** Sends the visitor to the payment provider's page for the plan; reports a failure in a toast. */
export async function startCheckout(request: CheckoutRequest, failureTitle: string) {
  try {
    const { url } = await upgradeApi.checkout(request);
    window.location.assign(url);
  } catch (error) {
    toast.error(failureTitle, { description: errorMessage(error) });
  }
}

/** Sends an Enterprise inquiry; resolves to null on success or the message to show in the form. */
export async function sendSalesInquiry(request: SalesInquiryRequest, fallback: string): Promise<string | null> {
  try {
    await upgradeApi.salesInquiry(request);
    return null;
  } catch (error) {
    return errorMessage(error) ?? fallback;
  }
}
