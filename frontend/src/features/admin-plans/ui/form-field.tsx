"use client";

import type { ComponentProps, ReactNode } from "react";

import { Field, FieldContent } from "@/components/ui/field";
import { FieldDescription, FieldError, FieldLabel } from "@/components/ui/field-text";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";

import { fieldAria } from "./field-aria";

type Wiring = { id: string; label: ReactNode; description?: ReactNode; error?: string };

/** Label, hint and announced error around one control, with ids wired for screen readers. */
export function FormField({ id, label, description, error, children }: Wiring & { children: ReactNode }) {
  return (
    <Field data-invalid={error ? true : undefined}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      {children}
      {description ? <FieldDescription id={`${id}-description`}>{description}</FieldDescription> : null}
      {error ? <FieldError id={`${id}-error`}>{error}</FieldError> : null}
    </Field>
  );
}

export function TextField({ id, label, description, error, ...input }: Wiring & ComponentProps<typeof Input>) {
  return (
    <FormField id={id} label={label} description={description} error={error}>
      <Input {...input} {...fieldAria(id, description, error)} />
    </FormField>
  );
}

export function TextAreaField({ id, label, description, error, ...input }: Wiring & ComponentProps<typeof Textarea>) {
  return (
    <FormField id={id} label={label} description={description} error={error}>
      <Textarea {...input} {...fieldAria(id, description, error)} />
    </FormField>
  );
}

/** A labelled on/off setting with a short explanation. */
export function SwitchField({
  id,
  label,
  description,
  checked,
  disabled,
  onCheckedChange,
}: {
  id: string;
  label: string;
  description: string;
  checked: boolean;
  disabled?: boolean;
  onCheckedChange: (checked: boolean) => void;
}) {
  return (
    <Field orientation="horizontal" className="rounded-lg border p-3" data-disabled={disabled ? true : undefined}>
      <FieldContent>
        <FieldLabel htmlFor={id}>{label}</FieldLabel>
        <FieldDescription id={`${id}-description`}>{description}</FieldDescription>
      </FieldContent>
      <Switch
        id={id}
        checked={checked}
        disabled={disabled}
        onCheckedChange={onCheckedChange}
        aria-describedby={`${id}-description`}
      />
    </Field>
  );
}
