"use client";

import { useTranslations } from "use-intl";

import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const ALL = "all";

type Option = { id: string; label: string };

/**
 * A compact "Label: value" filter for a list's toolbar, with an "all" choice first that maps to null.
 * `allLabel` names that choice; it defaults to "All" in the interface language.
 */
export function FilterSelect({
  label,
  value,
  options,
  onChange,
  allLabel,
}: {
  label: string;
  value: string | null;
  options: readonly Option[];
  onChange: (value: string | null) => void;
  allLabel?: string;
}) {
  const t = useTranslations("pages");
  return (
    <Select value={value ?? ALL} onValueChange={(next) => onChange(next === ALL ? null : next)}>
      <SelectTrigger size="sm" aria-label={label}>
        <span className="text-muted-foreground">{t("filter.label", { label })}</span>
        <SelectValue />
      </SelectTrigger>
      <SelectContent position="popper" align="start">
        <SelectGroup>
          <SelectItem value={ALL}>{allLabel ?? t("filter.all")}</SelectItem>
          {options.map((option) => (
            <SelectItem key={option.id} value={option.id}>
              {option.label}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  );
}
