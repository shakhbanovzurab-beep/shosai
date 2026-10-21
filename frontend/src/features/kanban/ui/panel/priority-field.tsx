"use client";

import { useTranslations } from "use-intl";

import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

import { PRIORITIES, type Priority } from "../../domain/tasks-contract";

const NONE = "none";

/** Приоритет или «без приоритета». */
export function PriorityField({
  value,
  labelId,
  disabled,
  onChange,
}: {
  value: Priority | null;
  labelId: string;
  disabled: boolean;
  onChange: (priority: Priority | null) => void;
}) {
  const t = useTranslations("kanban");
  return (
    <Select
      value={value ?? NONE}
      disabled={disabled}
      onValueChange={(next) => onChange(next === NONE ? null : (next as Priority))}
    >
      <SelectTrigger size="sm" aria-labelledby={labelId} className="min-w-36">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          {PRIORITIES.map((priority) => (
            <SelectItem key={priority} value={priority}>
              {t(`priority.${priority}`)}
            </SelectItem>
          ))}
          <SelectItem value={NONE}>{t("priority.none")}</SelectItem>
        </SelectGroup>
      </SelectContent>
    </Select>
  );
}
