"use client";

import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldLegend, FieldSet } from "@/components/ui/field";
import { FieldDescription, FieldError, FieldLabel } from "@/components/ui/field-text";
import { InputGroup, InputGroupAddon, InputGroupInput, InputGroupText } from "@/components/ui/input-group";

import { CURRENCIES, CURRENCY_NAME, CURRENCY_SYMBOL, type Currency, type DiscountType } from "../domain/contract";
import { type PromoValues, promoInputId } from "../domain/promo-form-values";
import { Choice } from "./choice";
import { fieldAria } from "./field-aria";
import { FormField } from "./form-field";

const DISCOUNT_OPTIONS: { value: DiscountType; label: string }[] = [
  { value: "percent", label: "Процент — в любой валюте" },
  { value: "fixed", label: "Фиксированная сумма" },
];
const FIXED_HINT = "Отметьте валюты, в которых действует код: при оплате в других валютах он не примется.";

type DiscountFieldsProps = {
  values: PromoValues;
  errors: Record<string, string>;
  disabled: boolean;
  onType: (type: DiscountType) => void;
  onPercent: (value: string) => void;
  onCurrency: (currency: Currency, checked: boolean) => void;
  onAmount: (currency: Currency, value: string) => void;
};

function AmountRow({
  currency,
  values,
  errors,
  disabled,
  onCurrency,
  onAmount,
}: { currency: Currency } & DiscountFieldsProps) {
  const checkboxId = currency === CURRENCIES[0] ? promoInputId("amounts_off") : `promo-currency-${currency}`;
  const inputId = promoInputId(`amounts_off.${currency}`);
  const chosen = values.currencies.includes(currency);
  const error = errors[`amounts_off.${currency}`];
  return (
    <div className="grid grid-cols-[8rem_minmax(0,12rem)] items-center gap-3">
      <Field orientation="horizontal">
        <Checkbox
          id={checkboxId}
          checked={chosen}
          disabled={disabled}
          onCheckedChange={(checked) => onCurrency(currency, checked === true)}
        />
        <FieldLabel htmlFor={checkboxId} className="font-normal">
          {CURRENCY_NAME[currency]}
        </FieldLabel>
      </Field>
      <InputGroup data-disabled={!chosen || disabled ? true : undefined}>
        <InputGroupInput
          {...fieldAria(inputId, null, error)}
          aria-label={`Скидка, ${CURRENCY_NAME[currency].toLowerCase()}`}
          inputMode="decimal"
          autoComplete="off"
          placeholder={chosen ? "0" : "Не действует"}
          disabled={!chosen || disabled}
          value={chosen ? values.amounts[currency] : ""}
          onChange={(event) => onAmount(currency, event.target.value)}
        />
        <InputGroupAddon align="inline-end">
          <InputGroupText>{CURRENCY_SYMBOL[currency]}</InputGroupText>
        </InputGroupAddon>
      </InputGroup>
      {error ? (
        <FieldError id={`${inputId}-error`} className="col-span-2">
          {error}
        </FieldError>
      ) : null}
    </div>
  );
}

/** Discount type, then a percent or a fixed amount per chosen currency. */
export function DiscountFields(props: DiscountFieldsProps) {
  const { values, errors, disabled, onType, onPercent } = props;
  const percentId = promoInputId("percent_off");
  return (
    <FieldSet>
      <FieldLegend>Скидка</FieldLegend>
      <Choice
        name="promo-discount-type"
        label="Тип скидки"
        value={values.discount_type}
        options={DISCOUNT_OPTIONS}
        disabled={disabled}
        onChange={onType}
      />
      {values.discount_type === "percent" ? (
        <FormField id={percentId} label="Размер" description="От 1 до 100." error={errors.percent_off}>
          <InputGroup className="sm:max-w-40">
            <InputGroupInput
              {...fieldAria(percentId, "От 1 до 100.", errors.percent_off)}
              inputMode="numeric"
              autoComplete="off"
              disabled={disabled}
              value={values.percent_off}
              onChange={(event) => onPercent(event.target.value)}
            />
            <InputGroupAddon align="inline-end">
              <InputGroupText>%</InputGroupText>
            </InputGroupAddon>
          </InputGroup>
        </FormField>
      ) : (
        <fieldset className="flex flex-col gap-2" aria-describedby="promo-amounts-hint">
          <legend className="sr-only">Сумма скидки по валютам</legend>
          {CURRENCIES.map((currency) => (
            <AmountRow key={currency} currency={currency} {...props} />
          ))}
          <FieldDescription id="promo-amounts-hint">{FIXED_HINT}</FieldDescription>
          {errors.amounts_off ? <FieldError>{errors.amounts_off}</FieldError> : null}
        </fieldset>
      )}
    </FieldSet>
  );
}
