"use client";

import { type FormEvent, useState, useTransition } from "react";

import { Shuffle } from "lucide-react";

import { FieldLegend, FieldSet } from "@/components/ui/field";
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from "@/components/ui/input-group";

import { type Plan, PROMO_CODE_MAX, type PromoScope } from "../domain/contract";
import { randomCode } from "../domain/promo-code";
import {
  initialPromoValues,
  type PromoFormTarget,
  type PromoValues,
  promoCandidateOf,
  promoFieldKey,
  promoInputId,
} from "../domain/promo-form-values";
import { promoDraftSchema } from "../domain/promo-schema";
import { savePromo } from "../model/promo-actions";
import { Choice } from "./choice";
import { DiscountFields } from "./discount-fields";
import { fieldAria } from "./field-aria";
import { FormField } from "./form-field";
import { FormFooter } from "./form-footer";
import { errorsByKey, focusFirst, withoutKey } from "./form-helpers";
import { PlanPicker } from "./plan-picker";
import { PromoRulesFields } from "./promo-rules-fields";

const SCOPE_OPTIONS: { value: PromoScope; label: string }[] = [
  { value: "all", label: "Все тарифы" },
  { value: "plans", label: "Только выбранные" },
];
const CODE_HINT = "Латиница, цифры, дефис и подчёркивание. Код сохраняется заглавными буквами.";

/** Creates, edits or copies a promo code; validates with the API's schema before sending. */
export function PromoForm({ target, plans, onDone }: { target: PromoFormTarget; plans: Plan[]; onDone: () => void }) {
  const [values, setValues] = useState<PromoValues>(() => initialPromoValues(target));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  /** Updates one value and clears the errors shown for it (`errorKey` when it differs from the key). */
  function set<K extends keyof PromoValues>(key: K, value: PromoValues[K], errorKey: string = key) {
    setValues((current) => ({ ...current, [key]: value }));
    setErrors((current) => withoutKey(withoutKey(current, errorKey), key));
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    const parsed = promoDraftSchema.safeParse(promoCandidateOf(values));
    if (!parsed.success) {
      const found = errorsByKey(parsed.error, promoFieldKey);
      setErrors(found);
      focusFirst(found, promoInputId);
      return;
    }
    startTransition(async () => {
      const failure = await savePromo(target, parsed.data);
      if (failure === null) onDone();
      else setFormError(failure);
    });
  }

  const codeId = promoInputId("code");

  return (
    <form noValidate onSubmit={submit} className="flex min-h-0 flex-col gap-6">
      <FormField id={codeId} label="Код" description={CODE_HINT} error={errors.code}>
        <InputGroup>
          <InputGroupInput
            {...fieldAria(codeId, CODE_HINT, errors.code)}
            value={values.code}
            disabled={pending}
            autoComplete="off"
            spellCheck={false}
            maxLength={PROMO_CODE_MAX}
            className="font-mono uppercase"
            onChange={(event) => set("code", event.target.value.toUpperCase())}
          />
          <InputGroupAddon align="inline-end">
            <InputGroupButton disabled={pending} onClick={() => set("code", randomCode(8))}>
              <Shuffle data-icon="inline-start" />
              Сгенерировать
            </InputGroupButton>
          </InputGroupAddon>
        </InputGroup>
      </FormField>

      <DiscountFields
        values={values}
        errors={errors}
        disabled={pending}
        onType={(type) => set("discount_type", type, "amounts_off")}
        onPercent={(value) => set("percent_off", value)}
        onCurrency={(currency, checked) =>
          set(
            "currencies",
            checked ? [...values.currencies, currency] : values.currencies.filter((c) => c !== currency),
            "amounts_off",
          )
        }
        onAmount={(currency, value) =>
          set("amounts", { ...values.amounts, [currency]: value }, `amounts_off.${currency}`)
        }
      />

      <FieldSet>
        <FieldLegend>Тарифы</FieldLegend>
        <Choice
          name="promo-scope"
          label="К каким тарифам применяется код"
          value={values.scope}
          options={SCOPE_OPTIONS}
          disabled={pending}
          onChange={(scope) => set("scope", scope, "plan_ids")}
        />
        {values.scope === "plans" ? (
          <PlanPicker
            plans={plans}
            selected={values.plan_ids}
            firstId={promoInputId("plan_ids")}
            error={errors.plan_ids}
            disabled={pending}
            onToggle={(id, checked) =>
              set("plan_ids", checked ? [...values.plan_ids, id] : values.plan_ids.filter((planId) => planId !== id))
            }
          />
        ) : (
          <p className="text-muted-foreground text-sm">Код действует и для тарифов, которые появятся позже.</p>
        )}
      </FieldSet>

      <PromoRulesFields
        values={values}
        errors={errors}
        disabled={pending}
        onText={(key, value) => set(key, value)}
        onPeriod={(period) => set("billing_period", period)}
        onFlag={(key, value) => set(key, value)}
      />

      <FormFooter
        error={formError}
        pending={pending}
        submitLabel={target.mode === "edit" ? "Сохранить" : "Создать промокод"}
      />
    </form>
  );
}
