"use client";

import { Minus, Plus } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";

type SeatPickerProps = {
  id: string;
  value: number;
  min: number;
  max: number | null;
  onChange: (value: number) => void;
};

const clamp = (value: number, min: number, max: number | null) => Math.min(Math.max(value, min), max ?? value);

/** How many users to buy for: − and + buttons around a number field, kept within the plan's range. */
export function SeatPicker({ id, value, min, max, onChange }: SeatPickerProps) {
  const t = useTranslations("upgrade");
  return (
    <div className="flex items-center justify-between gap-3">
      <label htmlFor={id} className="text-sm">
        {t("seats.label")}
      </label>
      <div className="flex items-center gap-1">
        <Button
          variant="outline"
          size="icon-sm"
          aria-label={t("seats.fewer")}
          disabled={value <= min}
          onClick={() => onChange(clamp(value - 1, min, max))}
        >
          <Minus />
        </Button>
        <input
          id={id}
          type="number"
          inputMode="numeric"
          min={min}
          max={max ?? undefined}
          value={value}
          onChange={(event) => {
            const next = Number.parseInt(event.currentTarget.value, 10);
            if (Number.isFinite(next)) onChange(clamp(next, min, max));
          }}
          className="h-8 w-14 rounded-md border bg-background text-center text-sm tabular-nums outline-none [appearance:textfield] focus-visible:ring-3 focus-visible:ring-ring/50 [&::-webkit-inner-spin-button]:appearance-none"
        />
        <Button
          variant="outline"
          size="icon-sm"
          aria-label={t("seats.more")}
          disabled={max !== null && value >= max}
          onClick={() => onChange(clamp(value + 1, min, max))}
        >
          <Plus />
        </Button>
      </div>
    </div>
  );
}
