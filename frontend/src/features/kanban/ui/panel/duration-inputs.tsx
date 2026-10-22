"use client";

import { type KeyboardEvent, useId } from "react";

import { useLocale } from "use-intl";

import { InputGroup, InputGroupAddon, InputGroupInput, InputGroupText } from "@/components/ui/input-group";
import { unitLabel } from "@/i18n/format-units";

import type { DurationDraft } from "../../domain/duration-input";

/** Длительность часами и минутами: два поля с подписями единиц на языке человека; `labelId` называет пару. */
export function DurationInputs({
  labelId,
  value,
  onChange,
  onKeyDown,
  disabled,
  invalid,
  errorId,
}: {
  labelId: string;
  value: DurationDraft;
  onChange: (value: DurationDraft) => void;
  onKeyDown?: (event: KeyboardEvent<HTMLInputElement>) => void;
  disabled?: boolean;
  invalid?: boolean;
  /** Id текста ошибки: поля ссылаются на него, пока ввод неверен. */
  errorId?: string;
}) {
  const locale = useLocale();
  const hoursId = useId();
  const minutesId = useId();
  const parts = [
    { key: "hours", id: hoursId, unit: "hour" },
    { key: "minutes", id: minutesId, unit: "minute" },
  ] as const;
  return (
    <div className="flex gap-2">
      {parts.map((part) => (
        <InputGroup key={part.key} className="w-24">
          <InputGroupInput
            inputMode="decimal"
            autoComplete="off"
            value={value[part.key]}
            disabled={disabled}
            aria-invalid={invalid ? true : undefined}
            aria-describedby={invalid ? errorId : undefined}
            aria-labelledby={`${labelId} ${part.id}`}
            className="tabular-nums"
            onChange={(event) => onChange({ ...value, [part.key]: event.currentTarget.value })}
            onKeyDown={onKeyDown}
          />
          <InputGroupAddon align="inline-end">
            <InputGroupText id={part.id}>{unitLabel(locale, part.unit)}</InputGroupText>
          </InputGroupAddon>
        </InputGroup>
      ))}
    </div>
  );
}
