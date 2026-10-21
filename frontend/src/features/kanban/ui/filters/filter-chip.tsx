"use client";

import type { ReactNode } from "react";

import { ChevronDown, X } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { ButtonGroup } from "@/components/ui/button-group";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

/**
 * Фильтр одного поля: чип открывает выбор; включённый — `secondary`, говорит, что отсеивает («Приоритет: Высокий,
 * Низкий»), и несёт свою кнопку сброса.
 */
export function FilterChip({
  field,
  active,
  onClear,
  children,
}: {
  field: string;
  /** Что выбрано, словами; null — фильтр поля выключен. */
  active: string | null;
  onClear: () => void;
  children: ReactNode;
}) {
  const t = useTranslations("kanbanFilters");
  const trigger = (
    <PopoverTrigger asChild>
      <Button variant={active ? "secondary" : "outline"} size="sm" className="max-w-72">
        <span dir="auto" className="truncate">
          {active ? t("active", { field, values: active }) : field}
        </span>
        <ChevronDown data-icon="inline-end" />
      </Button>
    </PopoverTrigger>
  );
  return (
    <Popover>
      {active ? (
        <ButtonGroup className="shrink-0">
          {trigger}
          <Button variant="secondary" size="icon-sm" aria-label={t("clearOne", { field })} onClick={onClear}>
            <X />
          </Button>
        </ButtonGroup>
      ) : (
        <div className="shrink-0">{trigger}</div>
      )}
      <PopoverContent align="start" className="w-64 p-3">
        {children}
      </PopoverContent>
    </Popover>
  );
}
