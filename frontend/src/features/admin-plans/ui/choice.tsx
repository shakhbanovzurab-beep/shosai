"use client";

import { Field } from "@/components/ui/field";
import { FieldLabel } from "@/components/ui/field-text";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";

type ChoiceProps<T extends string> = {
  name: string;
  label: string;
  value: T;
  options: { value: T; label: string }[];
  disabled: boolean;
  onChange: (value: T) => void;
};

/** A short inline set of radio options, e.g. discount type or billing period. */
export function Choice<T extends string>({ name, label, value, options, disabled, onChange }: ChoiceProps<T>) {
  return (
    <RadioGroup
      aria-label={label}
      value={value}
      disabled={disabled}
      onValueChange={(next) => {
        const option = options.find((o) => o.value === next);
        if (option) onChange(option.value);
      }}
      className="flex flex-wrap gap-x-5 gap-y-2"
    >
      {options.map((option) => (
        <Field key={option.value} orientation="horizontal" className="w-auto">
          <RadioGroupItem value={option.value} id={`${name}-${option.value}`} />
          <FieldLabel htmlFor={`${name}-${option.value}`} className="font-normal">
            {option.label}
          </FieldLabel>
        </Field>
      ))}
    </RadioGroup>
  );
}
