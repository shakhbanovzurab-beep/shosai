"use client";

import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Field } from "@/components/ui/field";
import { FieldError, FieldLabel } from "@/components/ui/field-text";

import type { Plan } from "../domain/contract";

type PlanPickerProps = {
  plans: Plan[];
  selected: string[];
  /** Given to the first checkbox, so a validation error can move focus here. */
  firstId: string;
  error?: string;
  disabled: boolean;
  onToggle: (id: string, checked: boolean) => void;
};

/** Plans a code can be scoped to: those on sale plus any archived ones it already has. */
export function PlanPicker({ plans, selected, firstId, error, disabled, onToggle }: PlanPickerProps) {
  const chosen = new Set(selected);
  const options = plans.filter((plan) => !plan.archived || chosen.has(plan.id));
  const errorId = `${firstId}-error`;
  return (
    <div className="flex flex-col gap-2">
      <fieldset
        aria-describedby={error ? errorId : undefined}
        className="grid gap-2 rounded-lg border p-3 sm:grid-cols-2"
      >
        <legend className="sr-only">Тарифы промокода</legend>
        {options.map((plan, index) => {
          const id = index === 0 ? firstId : `promo-plan-${plan.id}`;
          return (
            <Field key={plan.id} orientation="horizontal">
              <Checkbox
                id={id}
                checked={chosen.has(plan.id)}
                disabled={disabled}
                onCheckedChange={(checked) => onToggle(plan.id, checked === true)}
              />
              <FieldLabel htmlFor={id} className="font-normal">
                {plan.name}
                {plan.archived ? <Badge variant="outline">в архиве</Badge> : null}
                {!plan.archived && !plan.is_active ? <Badge variant="outline">выключен</Badge> : null}
              </FieldLabel>
            </Field>
          );
        })}
      </fieldset>
      {error ? <FieldError id={errorId}>{error}</FieldError> : null}
    </div>
  );
}
