"use client";

import { useFormatter, useTranslations } from "use-intl";

import { DUE_BUCKETS, type DueBucket, UNASSIGNED } from "../../domain/filter-contract";
import { assigneeKey } from "../../domain/filter-rules";
import { PRIORITIES, type Priority } from "../../domain/tasks-contract";
import { useBoardSelector } from "../../model/board-hooks";
import { OwnerAvatar } from "../task-owner";
import { type Choice, ChoiceList } from "./choice-list";
import { setFilter } from "./filter-address";
import { FilterChip } from "./filter-chip";
import { useActiveFilter } from "./use-visible-cards";

/** Что выбрано, словами: метки выбранных через запятую, как принято в языке. */
export function useChosenText() {
  const format = useFormatter();
  return (choices: Choice[], selected: string[]) => {
    if (selected.length === 0) return null;
    const chosen = new Set(selected);
    return format.list(
      choices.filter((choice) => chosen.has(choice.value)).map((choice) => choice.label),
      { type: "unit" },
    );
  };
}

/** Чип с неизменным набором выборов: срок, приоритет, повтор, поля времени. */
export function FixedChip<T extends string>({
  field,
  choices,
  selected,
  onChange,
}: {
  field: string;
  choices: Choice[];
  selected: T[];
  onChange: (selected: T[]) => void;
}) {
  const chosen = useChosenText();
  return (
    <FilterChip field={field} active={chosen(choices, selected)} onClear={() => onChange([])}>
      <ChoiceList legend={field} choices={choices} selected={selected} onChange={(next) => onChange(next as T[])} />
    </FilterChip>
  );
}

/** Люди, которые стоят исполнителями на доске: ключ и имя строкой, чтобы выбор был той же ссылкой. */
function usePeople(): { key: string; name: string }[] {
  const lines = useBoardSelector((s) => {
    const people = new Map<string, string>();
    for (const card of Object.values(s.cards))
      if (card.assignee) people.set(assigneeKey(card.assignee), card.assignee.name);
    return [...people]
      .map(([key, name]) => `${key}\u0001${name}`)
      .toSorted()
      .join("\u0002");
  });
  return lines
    ? lines.split("\u0002").map((line) => {
        const [key = "", name = ""] = line.split("\u0001");
        return { key, name };
      })
    : [];
}

export function AssigneeChip({ field }: { field: string }) {
  const t = useTranslations("kanbanFilters");
  const filter = useActiveFilter();
  const chosen = useChosenText();
  const choices: Choice[] = [
    ...usePeople().map(({ key, name }) => ({
      value: key,
      label: name,
      mark: <OwnerAvatar owner={{ user_id: null, name }} />,
    })),
    { value: UNASSIGNED, label: t("unassigned"), mark: <OwnerAvatar owner={null} /> },
  ];
  const change = (assignee: string[]) => setFilter((current) => ({ ...current, assignee }));
  return (
    <FilterChip field={field} active={chosen(choices, filter.assignee)} onClear={() => change([])}>
      <ChoiceList
        legend={field}
        choices={choices}
        selected={filter.assignee}
        onChange={change}
        searchLabel={t("findPerson")}
        emptyText={t("noPeople")}
      />
    </FilterChip>
  );
}

export function DueChip({ field }: { field: string }) {
  const t = useTranslations("kanbanFilters");
  const filter = useActiveFilter();
  const choices = DUE_BUCKETS.map((bucket) => ({ value: bucket, label: t(`due.${bucket}`) }));
  return (
    <FixedChip<DueBucket>
      field={field}
      choices={choices}
      selected={filter.due}
      onChange={(due) => setFilter((current) => ({ ...current, due }))}
    />
  );
}

export function PriorityChip({ field }: { field: string }) {
  const t = useTranslations("kanban");
  const filter = useActiveFilter();
  const choices = [...PRIORITIES, "none" as const].map((priority) => ({
    value: priority,
    label: t(`priority.${priority}`),
  }));
  return (
    <FixedChip<Priority | "none">
      field={field}
      choices={choices}
      selected={filter.priority}
      onChange={(priority) => setFilter((current) => ({ ...current, priority }))}
    />
  );
}

export function RepeatChip({ field }: { field: string }) {
  const t = useTranslations("kanbanFilters");
  const filter = useActiveFilter();
  const choices = (["yes", "no"] as const).map((value) => ({ value, label: t(`repeat.${value}`) }));
  return (
    <FixedChip<"yes" | "no">
      field={field}
      choices={choices}
      selected={filter.repeat}
      onChange={(repeat) => setFilter((current) => ({ ...current, repeat }))}
    />
  );
}
