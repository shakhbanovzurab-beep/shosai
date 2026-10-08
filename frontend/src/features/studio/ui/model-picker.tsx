"use client";

import { useState } from "react";

import { cn } from "cn";
import { ChevronsUpDown } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

import type { ModelInfo } from "../domain/contract";
import { byProvider } from "../domain/models";

/** A choice listed above the models, such as "Auto"; its id is passed to onChange like a model's. */
type PickerOption = { id: string; label: string; hint?: string };

type ModelPickerProps = {
  id: string;
  models: ModelInfo[];
  value: string | null;
  onChange: (modelId: string) => void;
  label: string;
  options?: PickerOption[];
};

function FrontierMark() {
  const t = useTranslations("studio");
  return (
    <Badge variant="outline" className="rounded-md px-1.5 font-normal text-[10px]">
      {t("picker.frontier")}
    </Badge>
  );
}

/** A searchable model select: type a provider, model name or id to narrow a long list. */
export function ModelPicker({ id, models, value, onChange, label, options = [] }: ModelPickerProps) {
  const t = useTranslations("studio");
  const format = useFormatter();
  const [open, setOpen] = useState(false);
  const selected = models.find((m) => m.id === value);
  const selectedOption = options.find((o) => o.id === value);
  const choose = (choice: string) => {
    onChange(choice);
    setOpen(false);
  };

  return (
    // Modal so the list scrolls even inside a dialog (Settings), whose scroll lock would otherwise swallow the wheel.
    <Popover open={open} onOpenChange={setOpen} modal>
      <PopoverTrigger asChild>
        <Button
          id={id}
          variant="outline"
          role="combobox"
          aria-expanded={open}
          aria-label={selected ? undefined : label}
          className="w-full justify-between font-normal"
        >
          <span
            className={cn("flex min-w-0 items-center gap-2", !selected && !selectedOption && "text-muted-foreground")}
          >
            <span className="truncate">
              {selected
                ? `${selected.provider} • ${selected.name}`
                : (selectedOption?.label ?? t("picker.placeholder"))}
            </span>
            {selected?.tier === "frontier" ? <FrontierMark /> : null}
          </span>
          <ChevronsUpDown className="opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-(--radix-popover-trigger-width) min-w-72 p-0">
        <Command>
          <CommandInput placeholder={t("picker.search")} />
          <CommandList>
            <CommandEmpty>{t("picker.empty")}</CommandEmpty>
            {options.length > 0 ? (
              <CommandGroup>
                {options.map((option) => (
                  <CommandItem
                    key={option.id}
                    value={option.id}
                    keywords={[option.label]}
                    data-checked={option.id === value}
                    onSelect={() => choose(option.id)}
                  >
                    <span className="truncate">{option.label}</span>
                    {option.hint ? <span className="truncate text-muted-foreground text-xs">{option.hint}</span> : null}
                  </CommandItem>
                ))}
              </CommandGroup>
            ) : null}
            {byProvider(models).map(([provider, items]) => (
              <CommandGroup key={provider} heading={provider}>
                {items.map((model) => (
                  <CommandItem
                    key={model.id}
                    value={model.id}
                    keywords={[model.provider, model.name]}
                    data-checked={model.id === value}
                    onSelect={() => choose(model.id)}
                  >
                    <span className="truncate">{model.name}</span>
                    {model.tier === "frontier" ? <FrontierMark /> : null}
                    {/* The longest answer the model may write, in tokens: "64K", "6.4万". */}
                    <span className="ms-auto shrink-0 text-muted-foreground text-xs tabular-nums">
                      {format.number(model.max_output_tokens, "compact")}
                    </span>
                  </CommandItem>
                ))}
              </CommandGroup>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
