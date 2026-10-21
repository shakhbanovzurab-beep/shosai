"use client";

import { type ReactNode, useId, useState } from "react";

import { useTranslations } from "use-intl";

import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export type Choice = { value: string; label: string; mark?: ReactNode };

// Короткий список выбирают глазами; длинный — ещё и поиском.
const SEARCH_FROM = 8;

const toggled = (selected: string[], value: string) =>
  selected.includes(value) ? selected.filter((item) => item !== value) : [...selected, value];

/** Выборы одного поля флажками: любой из отмеченных подходит. */
export function ChoiceList({
  legend,
  choices,
  selected,
  onChange,
  searchLabel,
  emptyText,
}: {
  legend: string;
  choices: Choice[];
  selected: string[];
  onChange: (selected: string[]) => void;
  searchLabel?: string;
  emptyText?: string;
}) {
  const t = useTranslations("kanbanFilters");
  const [query, setQuery] = useState("");
  const baseId = useId();
  const words = query.trim().toLocaleLowerCase();
  const shown = words ? choices.filter((choice) => choice.label.toLocaleLowerCase().includes(words)) : choices;
  const checked = new Set(selected);
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="sr-only">{legend}</legend>
      {choices.length >= SEARCH_FROM ? (
        <Input
          type="search"
          value={query}
          aria-label={searchLabel ?? t("searchPlaceholder")}
          placeholder={searchLabel ?? t("searchPlaceholder")}
          onChange={(event) => setQuery(event.currentTarget.value)}
        />
      ) : null}
      {shown.length === 0 ? <p className="text-muted-foreground text-sm">{emptyText ?? t("nothingFound")}</p> : null}
      <ul className="flex max-h-64 flex-col gap-1 overflow-y-auto">
        {shown.map((choice) => {
          const id = `${baseId}-${choice.value}`;
          return (
            <li key={choice.value} className="flex items-center gap-2 rounded-md px-1 py-1 hover:bg-muted">
              <Checkbox
                id={id}
                checked={checked.has(choice.value)}
                onCheckedChange={() => onChange(toggled(selected, choice.value))}
              />
              <Label htmlFor={id} className="flex min-w-0 flex-1 items-center gap-2 font-normal">
                {choice.mark}
                <span dir="auto" className="truncate">
                  {choice.label}
                </span>
              </Label>
            </li>
          );
        })}
      </ul>
    </fieldset>
  );
}
