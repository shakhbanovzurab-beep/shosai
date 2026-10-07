"use client";

import { Label } from "@/components/ui/label";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

interface PreferenceToggleProps<T extends string> {
  readonly label: string;
  readonly value: T;
  readonly options: readonly { value: T; label: string }[];
  readonly onChange: (value: T) => void;
}

/** One labelled single-choice preference; clicking the active option again keeps it selected. */
export function PreferenceToggle<T extends string>({ label, value, options, onChange }: PreferenceToggleProps<T>) {
  return (
    <div className="space-y-1">
      <Label className="font-medium text-xs">{label}</Label>
      <ToggleGroup
        size="sm"
        spacing={0}
        variant="outline"
        type="single"
        value={value}
        onValueChange={(next) => {
          const option = options.find((o) => o.value === next);
          if (option) onChange(option.value);
        }}
      >
        {options.map((option) => (
          <ToggleGroupItem key={option.value} value={option.value}>
            {option.label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  );
}
