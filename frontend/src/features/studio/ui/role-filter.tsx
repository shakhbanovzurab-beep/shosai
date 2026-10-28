"use client";

import { CircleHelp } from "lucide-react";
import { useTranslations } from "use-intl";

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

import type { StudioRole } from "../domain/contract";
import { ROLES } from "../domain/roles";

export type RoleFilterValue = StudioRole | "all";

const VALUES: RoleFilterValue[] = ["all", ...ROLES.map((role) => role.id)];

/** "All" or one role; hovering or focusing an option explains where that role is used. */
export function RoleFilter({
  value,
  onChange,
}: {
  value: RoleFilterValue;
  onChange: (value: RoleFilterValue) => void;
}) {
  const t = useTranslations("studioPrompts");
  const ts = useTranslations("studio");
  const options = VALUES.map((option) =>
    option === "all"
      ? { value: option, label: t("filter.all"), help: t("filter.allHelp") }
      : { value: option, label: ts(`roles.${option}.name`), help: ts(`roles.${option}.help`) },
  );

  return (
    <ToggleGroup
      type="single"
      variant="outline"
      spacing={0}
      value={value}
      onValueChange={(next) => {
        const option = VALUES.find((v) => v === next);
        if (option) onChange(option);
      }}
      aria-label={t("filter.label")}
      className="max-w-full overflow-x-auto"
    >
      {options.map((option) => (
        <Tooltip key={option.value}>
          <TooltipTrigger asChild>
            <ToggleGroupItem
              value={option.value}
              className="gap-1.5 whitespace-nowrap px-3 font-medium text-xs uppercase"
            >
              {option.label}
              <CircleHelp className="size-3.5 opacity-60" aria-hidden="true" />
            </ToggleGroupItem>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="max-w-72 text-sm leading-snug">
            {option.help}
          </TooltipContent>
        </Tooltip>
      ))}
    </ToggleGroup>
  );
}
