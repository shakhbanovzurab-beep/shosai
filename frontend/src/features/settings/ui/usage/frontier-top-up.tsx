"use client";

import { useState, useTransition } from "react";

import { cn } from "cn";
import { useFormatter, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

import type { TokenPack } from "../../domain/billing-contract";
import { buyTokenPack } from "../../model/billing-actions";
import { useTokenCount } from "./use-token-count";

/** Extra tokens for frontier models: what's left, and packs to buy more through the payment provider. */
export function FrontierTopUp({ balance, packs }: { balance: number; packs: TokenPack[] }) {
  const t = useTranslations("settingsUsage");
  const format = useFormatter();
  const { amount, tokens } = useTokenCount();
  // Only an explicit pick lives in state; until then the middle pack is suggested.
  const [picked, setPicked] = useState<string | null>(null);
  const selected = picked ?? packs[1]?.id ?? packs[0]?.id ?? "";
  const [pending, startTransition] = useTransition();

  const buy = () => startTransition(() => buyTokenPack(selected, t));

  return (
    <section aria-labelledby="extra-tokens-heading" className="flex flex-col gap-4 rounded-xl border p-5">
      <div className="flex flex-col gap-1">
        <h3 id="extra-tokens-heading" className="font-medium">
          {t("topUp.title")}
        </h3>
        <p className="text-muted-foreground text-sm">{t("topUp.description")}</p>
      </div>
      <p className="text-muted-foreground text-sm">
        {t.rich("topUp.balance", {
          count: balance,
          amount: amount(balance),
          big: (chunks) => (
            <span className="font-medium text-2xl text-foreground tabular-nums tracking-tight">{chunks}</span>
          ),
        })}
      </p>
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 font-medium text-sm">{t("topUp.buyMore")}</legend>
        <div className="grid gap-2 sm:grid-cols-3">
          {packs.map((pack) => (
            <label
              key={pack.id}
              className={cn(
                "flex cursor-pointer flex-col gap-0.5 rounded-lg border p-3 transition-colors has-focus-visible:outline-2 has-focus-visible:outline-ring",
                selected === pack.id ? "border-primary bg-primary/5" : "hover:bg-muted/50",
              )}
            >
              <input
                type="radio"
                name="token-pack"
                value={pack.id}
                checked={selected === pack.id}
                onChange={() => setPicked(pack.id)}
                className="sr-only"
              />
              <span className="font-medium text-sm">{tokens(pack.tokens)}</span>
              <span className="text-muted-foreground text-sm tabular-nums">
                {format.number(pack.price_cents / 100, { style: "currency", currency: pack.currency })}
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      <Button className="w-fit" disabled={!selected || pending} onClick={buy}>
        {pending ? <Spinner data-icon="inline-start" /> : null}
        {t("topUp.buy")}
      </Button>
    </section>
  );
}
