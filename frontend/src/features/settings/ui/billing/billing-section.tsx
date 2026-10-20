"use client";

import { CircleArrowUp } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { usePollingResource } from "@/hooks/use-polling-resource";
import { CALENDAR_DAY } from "@/i18n/calendar-days";
import { Link } from "@/lib/navigation";

import type { Billing } from "../../domain/billing-contract";
import { useSettingsDialog } from "../../model/dialog-store";
import { billingResource } from "../../model/settings-resources";
import { SectionState } from "../section-state";
import { InvoicesTable } from "./invoices-table";
import { PaymentMethods } from "./payment-methods";

function BillingContent({ billing }: { billing: Billing }) {
  const t = useTranslations("settingsBilling");
  const format = useFormatter();
  const close = useSettingsDialog((s) => s.close);
  const { plan } = billing;
  const price = format.number(plan.price_cents / 100, { style: "currency", currency: plan.currency });

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 rounded-xl border p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-1">
          <span className="flex items-center gap-2 font-medium">
            {t("plan.name", { plan: plan.name })}
            <Badge variant="secondary" className="rounded-md">
              {t("plan.current")}
            </Badge>
          </span>
          <span className="flex flex-wrap gap-x-1 text-muted-foreground text-sm">
            <span>{t("plan.price", { interval: plan.interval ?? "none", price })}</span>
            {billing.renews_at ? (
              <>
                <span aria-hidden="true">·</span>
                {/* Продление приходится на календарный день UTC: он и печатается в UTC. */}
                <span>
                  {t("plan.renews", { date: format.dateTime(new Date(billing.renews_at), "medium", CALENDAR_DAY) })}
                </span>
              </>
            ) : null}
          </span>
        </div>
        <Button asChild>
          <Link href="/app/upgrade" onClick={close}>
            <CircleArrowUp data-icon="inline-start" />
            {t("plan.upgrade")}
          </Link>
        </Button>
      </div>
      <PaymentMethods methods={billing.payment_methods} />
      <section aria-labelledby="billing-history" className="flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <h3 id="billing-history" className="font-medium text-muted-foreground text-xs uppercase tracking-wide">
            {t("history.title")}
          </h3>
          <p className="text-muted-foreground text-sm">{t("history.description")}</p>
        </div>
        <InvoicesTable invoices={billing.invoices} />
      </section>
    </div>
  );
}

export function BillingSection() {
  const state = usePollingResource(billingResource);
  return (
    <SectionState state={state} onRetry={() => void billingResource.refresh()}>
      {(billing) => <BillingContent billing={billing} />}
    </SectionState>
  );
}
