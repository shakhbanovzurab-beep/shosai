"use client";

import { useId, useState } from "react";

import { cn } from "cn";
import { useFormatter, useLocale, useTranslations } from "use-intl";

import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

import { parseNumberInput } from "../../domain/number-input";
import {
  type CustomSticker,
  STICKER_NUMBER_LIMIT,
  STICKER_TEXT_MAX,
  type StickerValue,
} from "../../domain/stickers-contract";
import { SWATCHES } from "../palette";
import { useValueLabel } from "./value-label";

const EMPTY = "empty";

type FieldProps = {
  sticker: CustomSticker;
  value: StickerValue | undefined;
  labelId: string;
  disabled: boolean;
  onChange: (value: StickerValue | null) => void;
};

/** Набор состояний: каждое со своим цветом, и «Не задано». */
function StateField({ sticker, value, labelId, disabled, onChange }: FieldProps) {
  const t = useTranslations("kanbanPanel");
  const valueLabel = useValueLabel(labelId);
  const current = value && "state_id" in value ? value.state_id : EMPTY;
  return (
    <Select
      value={current}
      disabled={disabled}
      onValueChange={(next) => onChange(next === EMPTY ? null : { state_id: next })}
    >
      <SelectTrigger size="sm" {...valueLabel} className="min-w-36">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          {sticker.states.map((state) => (
            <SelectItem key={state.id} value={state.id}>
              <span className={cn("size-2 rounded-full", SWATCHES[state.color].dot)} aria-hidden="true" />
              <span dir="auto">{state.name}</span>
            </SelectItem>
          ))}
          <SelectItem value={EMPTY}>{t("notSet")}</SelectItem>
        </SelectGroup>
      </SelectContent>
    </Select>
  );
}

/** То, что стоит в поле ввода: число как есть или текст; пустое — без значения. */
function shownText(value: StickerValue | undefined): string {
  if (!value) return "";
  if ("number" in value) return String(value.number);
  return "text" in value ? value.text : "";
}

/** Число или текст: сохраняется, когда человек уходит из поля или жмёт Enter; пустое очищает. Не число — ошибка у поля. */
function TypedField({ sticker, value, labelId, disabled, onChange }: FieldProps) {
  const t = useTranslations("kanbanPanel");
  const format = useFormatter();
  const locale = useLocale();
  const errorId = useId();
  const [invalid, setInvalid] = useState(false);
  const isNumber = sticker.kind === "number";
  const shown = shownText(value);
  const commit = (raw: string) => {
    const text = raw.trim();
    if (text === shown) return setInvalid(false);
    if (!text) return onChange(null);
    if (!isNumber) return onChange({ text: text.slice(0, STICKER_TEXT_MAX) });
    const parsed = parseNumberInput(text, locale);
    if (parsed === null || Math.abs(parsed) >= STICKER_NUMBER_LIMIT) return setInvalid(true);
    setInvalid(false);
    onChange({ number: Math.round(parsed * 100) / 100 });
  };
  return (
    <div className="flex flex-col gap-1">
      <Input
        key={shown}
        defaultValue={shown}
        disabled={disabled}
        aria-labelledby={labelId}
        aria-invalid={invalid || undefined}
        aria-describedby={invalid ? errorId : undefined}
        inputMode={isNumber ? "decimal" : undefined}
        maxLength={isNumber ? 20 : STICKER_TEXT_MAX}
        placeholder={isNumber ? t("value.number") : t("value.text")}
        title={isNumber && value && "number" in value ? format.number(value.number) : undefined}
        autoComplete="off"
        className="h-7 max-w-xs"
        dir="auto"
        onBlur={(event) => commit(event.currentTarget.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") event.currentTarget.blur();
          if (event.key === "Escape") {
            event.currentTarget.value = shown;
            setInvalid(false);
          }
        }}
      />
      {invalid ? (
        <p id={errorId} className="text-destructive text-xs">
          {t("value.invalidNumber")}
        </p>
      ) : null}
    </div>
  );
}

/** Своё поле доски — по его виду. */
export function ValueField(props: FieldProps) {
  return props.sticker.kind === "states" ? <StateField {...props} /> : <TypedField {...props} />;
}
