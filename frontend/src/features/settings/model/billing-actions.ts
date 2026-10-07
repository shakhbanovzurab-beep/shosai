"use client";

import { toast } from "sonner";

import { errorMessage } from "@/lib/errors";

import { settingsApi } from "../api/settings-api";
import type { BillingPortalRequest } from "../domain/billing-contract";
import type { BillingWords, UsageWords } from "./words";

/** Sends the user to the payment provider's secure page; card numbers never pass through our UI. */
export async function openPaymentPage(body: BillingPortalRequest, t: BillingWords) {
  try {
    const { url } = await settingsApi.billingPortal(body);
    window.location.assign(url);
  } catch (error) {
    toast.error(t("payment.openFailed"), { description: errorMessage(error) });
  }
}

/** Starts buying a pack of extra frontier tokens on the payment provider's checkout page. */
export async function buyTokenPack(packId: string, t: UsageWords) {
  try {
    const { url } = await settingsApi.topUp({ pack_id: packId });
    window.location.assign(url);
  } catch (error) {
    toast.error(t("topUp.failed"), { description: errorMessage(error) });
  }
}
