"use client";

import { useId } from "react";

import { cn } from "cn";
import { useFormatter, useTranslations } from "use-intl";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

import { EMPTY_STATE, type NumberFilter } from "../../domain/filter-contract";
import type { CustomSticker } from "../../domain/stickers-contract";
import { SWATCHES } from "../palette";
import { type Choice, ChoiceList } from "./choice-list";
import { setFilter } from "./filter-address";
import { FilterChip } from "./filter-chip";
import { useChosenText } from "./system-chips";
import { useActiveFilter } from "./use-visible-cards";

/** Набор состояний: любое из отмеченных или «Пусто». */
export function StatesChip({ sticker }: { sticker: CustomSticker }) {
  const t = useTranslations("kanbanFilters");
  const filter = useActiveFilter();
  const chosen = useChosenText();
  const selected = filter.states[sticker.id] ?? [];
  const choices: Choice[] = [
    ...sticker.states.map((state) => ({
      value: state.id,
      label: state.name,
      mark: <span className={cn("size-2.5 shrink-0 rounded-full", SWATCHES[state.color].dot)} aria-hidden="true" />,
    })),
    { value: EMPTY_STATE, label: t("empty") },
  ];
  const change = (next: string[]) =>
    setFilter((current) => ({ ...current, states: { ...current.states, [sticker.id]: next } }));
  return (
    <FilterChip field={sticker.name} active={chosen(choices, selected)} onClear={() => change([])}>
      <ChoiceList
        legend={sticker.name}
        choices={choices}
        selected={selected}
        onChange={change}
        searchLabel={t("findState")}
      />
    </FilterChip>
  );
}

/** Выбранный вид числового фильтра — с пустыми границами у «В пределах». */
function numberOf(mode: string): NumberFilter | null {
  if (mode === "empty" || mode === "set") return { mode };
  return mode === "range" ? { mode, from: null, to: null } : null;
}

/** Запись без одного ключа. */
function withoutKey<T>(record: Record<string, T>, key: string): Record<string, T> {
  return Object.fromEntries(Object.entries(record).filter(([id]) => id !== key));
}

const bound = (text: string) => (text.trim() === "" || !Number.isFinite(Number(text)) ? null : Number(text));

/** Число: пусто, не пусто или в пределах «от — до» (любая граница может отсутствовать). */
export function NumberChip({ sticker }: { sticker: CustomSticker }) {
  const t = useTranslations("kanbanFilters");
  const format = useFormatter();
  const filter = useActiveFilter();
  const fromId = useId();
  const toId = useId();
  const current = filter.numbers[sticker.id];
  const change = (next: NumberFilter | null) =>
    setFilter((state) => {
      const numbers = withoutKey(state.numbers, sticker.id);
      return { ...state, numbers: next ? { ...numbers, [sticker.id]: next } : numbers };
    });
  const range = current?.mode === "range" ? current : null;
  const n = (value: number | null) => (value === null ? "" : format.number(value));
  const rangeText = () => {
    if (!range || (range.from === null && range.to === null)) return t("number.range");
    if (range.to === null) return t("number.atLeast", { from: n(range.from) });
    return range.from === null
      ? t("number.atMost", { to: n(range.to) })
      : t("number.rangeValue", { from: n(range.from), to: n(range.to) });
  };
  const activeText = () => {
    if (!current) return null;
    return current.mode === "range" ? rangeText() : t(`number.${current.mode}`);
  };
  return (
    <FilterChip field={sticker.name} active={activeText()} onClear={() => change(null)}>
      <div className="flex flex-col gap-3">
        <ToggleGroup
          type="single"
          size="sm"
          variant="outline"
          aria-label={t("number.label")}
          value={current?.mode ?? ""}
          onValueChange={(mode) => change(numberOf(mode))}
          className="flex-wrap"
        >
          {(["empty", "set", "range"] as const).map((mode) => (
            <ToggleGroupItem key={mode} value={mode}>
              {t(`number.${mode}`)}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        {range ? (
          <div className="grid grid-cols-2 gap-2">
            {(["from", "to"] as const).map((edge) => (
              <div key={edge} className="flex flex-col gap-1">
                <Label htmlFor={edge === "from" ? fromId : toId} className="font-normal text-xs">
                  {t(`number.${edge}`)}
                </Label>
                <Input
                  id={edge === "from" ? fromId : toId}
                  type="number"
                  inputMode="decimal"
                  defaultValue={range[edge] ?? ""}
                  onChange={(event) => change({ ...range, [edge]: bound(event.currentTarget.value) })}
                />
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </FilterChip>
  );
}

/** Текст: карточки, в которых значение поля содержит набранное. */
export function TextChip({ sticker }: { sticker: CustomSticker }) {
  const t = useTranslations("kanbanFilters");
  const filter = useActiveFilter();
  const inputId = useId();
  const text = filter.texts[sticker.id] ?? "";
  const change = (next: string) => setFilter((state) => ({ ...state, texts: { ...state.texts, [sticker.id]: next } }));
  return (
    <FilterChip field={sticker.name} active={text.trim() ? `“${text.trim()}”` : null} onClear={() => change("")}>
      <div className="flex flex-col gap-1">
        <Label htmlFor={inputId} className="font-normal text-xs">
          {t("text.label")}
        </Label>
        <Input
          id={inputId}
          dir="auto"
          value={text}
          placeholder={t("text.placeholder")}
          onChange={(event) => change(event.currentTarget.value)}
        />
      </div>
    </FilterChip>
  );
}
