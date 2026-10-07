"use client";

import { type FormEvent, useState, useTransition } from "react";

import { FieldGroup, FieldLegend, FieldSet } from "@/components/ui/field";

import { type Currency, PLAN_AUDIENCE_LABEL, PLAN_AUDIENCES, PLAN_FEATURES_MAX, type Plan } from "../domain/contract";
import {
  EMPTY_PLAN,
  type PlanTextKey,
  type PlanValues,
  type PricePeriod,
  planCandidateOf,
  planFieldKey,
  planInputId,
  planValuesOf,
  yearlyHint,
} from "../domain/plan-form-values";
import { planDraftSchema } from "../domain/plan-schema";
import { slugify } from "../domain/slugify";
import { savePlan } from "../model/plan-actions";
import { Choice } from "./choice";
import { SwitchField, TextAreaField, TextField } from "./form-field";
import { FormFooter } from "./form-footer";
import { errorsByKey, focusFirst, withoutKey } from "./form-helpers";
import { PlanEntitlementsFields } from "./plan-entitlements-fields";
import { PriceGrid } from "./price-grid";

/** Creates a plan (`plan` null) or edits one; validates with the API's schema before sending. */
export function PlanForm({ plan, onDone }: { plan: Plan | null; onDone: () => void }) {
  const [values, setValues] = useState<PlanValues>(() => (plan ? planValuesOf(plan) : EMPTY_PLAN));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function set<K extends keyof PlanValues>(key: K, value: PlanValues[K]) {
    setValues((current) => {
      // A new plan's slug follows its name for as long as nobody has changed the slug by hand.
      const followName = key === "name" && plan === null && current.slug === slugify(current.name);
      return { ...current, [key]: value, ...(followName ? { slug: slugify(String(value)) } : {}) };
    });
    setErrors((current) => withoutKey(current, key));
  }

  function setPrice(period: PricePeriod, currency: Currency, value: string) {
    setValues((current) => ({ ...current, [period]: { ...current[period], [currency]: value } }));
    setErrors((current) => withoutKey(current, `${period}.${currency}`));
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    const parsed = planDraftSchema.safeParse(planCandidateOf(values));
    if (!parsed.success) {
      const found = errorsByKey(parsed.error, planFieldKey);
      setErrors(found);
      focusFirst(found, planInputId);
      return;
    }
    startTransition(async () => {
      const failure = await savePlan(plan, parsed.data);
      if (failure === null) onDone();
      else setFormError(failure);
    });
  }

  const text = (key: PlanTextKey) => ({
    id: planInputId(key),
    value: values[key],
    error: errors[key],
    disabled: pending,
    onChange: (event: { target: { value: string } }) => set(key, event.target.value),
  });

  return (
    <form noValidate onSubmit={submit} className="flex min-h-0 flex-col gap-6">
      <FieldGroup className="gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField label="Название" autoComplete="off" placeholder="Например, Pro" {...text("name")} />
          <TextField
            label="Slug"
            autoComplete="off"
            spellCheck={false}
            placeholder="pro"
            description="Для ссылок на оплату и приложений Leo."
            {...text("slug")}
            onChange={(event) => set("slug", event.target.value.toLowerCase())}
          />
        </div>
        <TextAreaField label="Описание" rows={2} placeholder="Кому подходит тариф" {...text("description")} />
      </FieldGroup>

      <FieldSet>
        <FieldLegend>Для кого</FieldLegend>
        <Choice
          name="plan-audience"
          label="Вкладка на странице тарифов"
          value={values.audience}
          options={PLAN_AUDIENCES.map((audience) => ({ value: audience, label: PLAN_AUDIENCE_LABEL[audience] }))}
          disabled={pending}
          onChange={(audience) => set("audience", audience)}
        />
        {values.audience === "team" ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField label="Пользователей от" inputMode="numeric" {...text("seats_min")} />
            <TextField
              label="Пользователей до"
              inputMode="numeric"
              description="Пустое поле — без верхней границы. Цена указывается за пользователя."
              {...text("seats_max")}
            />
          </div>
        ) : null}
      </FieldSet>

      <SwitchField
        id="plan-custom-pricing"
        label="Цена по договорённости"
        description="Вместо оплаты — заявка в отдел продаж. Цены не указываются, объёмы хранилища показываются как минимальные («от 250 ГБ»)."
        checked={values.custom_pricing}
        disabled={pending}
        onCheckedChange={(checked) => set("custom_pricing", checked)}
      />
      {values.custom_pricing ? null : (
        <PriceGrid values={values} errors={errors} hint={yearlyHint(values)} disabled={pending} onChange={setPrice} />
      )}

      <PlanEntitlementsFields
        text={text}
        capabilities={values.capabilities}
        disabled={pending}
        onCapability={(capability, enabled) => set("capabilities", { ...values.capabilities, [capability]: enabled })}
      />

      <FieldGroup className="gap-4">
        <TextAreaField
          label="Дополнительные строки карточки"
          rows={3}
          placeholder={"Everything in Basic"}
          description={`По одной на строку, не больше ${PLAN_FEATURES_MAX}. Показываются на странице тарифов перед лимитами, на языке страницы.`}
          {...text("features")}
        />
        <TextField
          label="Порядок сортировки"
          inputMode="numeric"
          className="sm:max-w-32"
          description="Меньше — левее на странице тарифов."
          {...text("sort_order")}
        />
        <div className="grid gap-3 sm:grid-cols-2">
          <SwitchField
            id="plan-is-active"
            label="Активен"
            description="Тариф можно купить."
            checked={values.is_active}
            disabled={pending}
            onCheckedChange={(checked) => set("is_active", checked)}
          />
          <SwitchField
            id="plan-is-featured"
            label="Рекомендуемый"
            description="Выделяется на странице тарифов."
            checked={values.is_featured}
            disabled={pending}
            onCheckedChange={(checked) => set("is_featured", checked)}
          />
        </div>
      </FieldGroup>

      <FormFooter error={formError} pending={pending} submitLabel={plan ? "Сохранить" : "Создать тариф"} />
    </form>
  );
}
