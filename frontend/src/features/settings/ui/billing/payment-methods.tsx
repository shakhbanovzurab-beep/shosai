"use client";

import { useTransition } from "react";

import { useFormatter, useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { CALENDAR_DAY } from "@/i18n/calendar-days";

import type { BillingPortalRequest, PaymentMethod } from "../../domain/billing-contract";
import { CARD_BRAND_NAMES } from "../../domain/names";
import { openPaymentPage } from "../../model/billing-actions";
import { CardBrandIcon } from "./card-brand-icon";

/** Sends the user to the payment provider's secure page; card numbers never pass through our UI. */
function useProviderRedirect() {
  const t = useTranslations("settingsBilling");
  const [pending, startTransition] = useTransition();
  const open = (body: BillingPortalRequest) => startTransition(() => openPaymentPage(body, t));
  return { pending, open };
}

function MethodRow({ method }: { method: PaymentMethod }) {
  const t = useTranslations("settingsBilling");
  const format = useFormatter();
  const { pending, open } = useProviderRedirect();
  const card = method.brand === "unknown" ? t("payment.unknownCard") : CARD_BRAND_NAMES[method.brand];
  const ending = { card, last4: method.last4 };
  // Срок карты — месяц: он собран в UTC и печатается в UTC, поэтому не сдвигается ни в каком поясе.
  const expires = format.dateTime(new Date(Date.UTC(method.exp_year, method.exp_month - 1)), "monthYear", CALENDAR_DAY);

  return (
    <li className="flex items-center gap-3 py-3">
      <CardBrandIcon brand={method.brand} />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="flex flex-wrap items-center gap-2 text-sm">
          <span className="font-medium">
            <span aria-hidden="true" dir="auto">
              {card} •••• {method.last4}
            </span>
            <span className="sr-only">{t("payment.endingIn", ending)}</span>
          </span>
          {method.is_default ? (
            <Badge variant="secondary" className="rounded-md">
              {t("payment.default")}
            </Badge>
          ) : null}
        </span>
        <span className="text-muted-foreground text-sm">{t("payment.expires", { date: expires })}</span>
      </div>
      <Button
        variant="outline"
        size="sm"
        disabled={pending}
        onClick={() => open({ intent: "update_payment_method", payment_method_id: method.id })}
        aria-label={t("payment.updateCard", ending)}
      >
        {pending ? <Spinner data-icon="inline-start" /> : null}
        {t("payment.update")}
      </Button>
    </li>
  );
}

export function PaymentMethods({ methods }: { methods: PaymentMethod[] }) {
  const t = useTranslations("settingsBilling");
  const { pending, open } = useProviderRedirect();

  return (
    <section aria-labelledby="payment-heading" className="flex flex-col gap-2">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
        <div className="flex flex-col gap-1">
          <h3 id="payment-heading" className="font-medium">
            {t("payment.title")}
          </h3>
          <p className="text-muted-foreground text-sm">{t("payment.description")}</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="w-fit shrink-0"
          disabled={pending}
          onClick={() => open({ intent: "add_payment_method" })}
        >
          {pending ? <Spinner data-icon="inline-start" /> : null}
          {t("payment.add")}
        </Button>
      </div>
      {methods.length > 0 ? (
        <ul className="divide-y">
          {methods.map((method) => (
            <MethodRow key={method.id} method={method} />
          ))}
        </ul>
      ) : (
        <p className="py-3 text-muted-foreground text-sm">{t("payment.empty")}</p>
      )}
    </section>
  );
}
