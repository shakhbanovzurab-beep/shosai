"use client";

import { cn } from "cn";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

import { COLORS, type Color } from "../../domain/stickers-contract";
import { SWATCHES } from "../palette";

/** Цвет состояния: точка открывает палитру с названиями цветов. */
export function StateColor({
  color,
  label,
  onChange,
}: {
  color: Color;
  label: string;
  onChange: (color: Color) => void;
}) {
  const t = useTranslations("kanban");
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="icon-sm" aria-label={label} className="shrink-0">
          <span className={cn("size-3 rounded-full", SWATCHES[color].dot)} aria-hidden="true" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-auto p-2">
        <ToggleGroup
          type="single"
          size="sm"
          aria-label={label}
          value={color}
          onValueChange={(next) => (next ? onChange(next as Color) : undefined)}
          className="flex-wrap"
        >
          {COLORS.map((item) => (
            <ToggleGroupItem key={item} value={item} aria-label={t(`colors.${item}`)} title={t(`colors.${item}`)}>
              <span className={cn("size-3 rounded-full", SWATCHES[item].dot)} aria-hidden="true" />
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </PopoverContent>
    </Popover>
  );
}
