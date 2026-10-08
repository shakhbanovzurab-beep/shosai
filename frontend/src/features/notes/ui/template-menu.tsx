"use client";

import { Plus, RefreshCw } from "lucide-react";
import { useTranslations } from "use-intl";

import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";

import type { NoteTemplate } from "../domain/templates";
import { TEMPLATE_ICON_GLYPHS } from "./template-icons";

/** Plain substring search over a template's name and description, so "pitch" finds only what says pitch. */
const containsQuery = (value: string, search: string, keywords?: string[]) => {
  const needle = search.trim().toLowerCase();
  return [value, ...(keywords ?? [])].some((text) => text.toLowerCase().includes(needle)) ? 1 : 0;
};

interface TemplateMenuProps {
  /** Leo's own layout, listed first. */
  readonly enhanced: NoteTemplate;
  readonly templates: NoteTemplate[];
  readonly value: NoteTemplate;
  readonly generating: boolean;
  readonly onPick: (template: NoteTemplate) => void;
  readonly onRegenerate: () => void;
  readonly onNewTemplate: () => void;
}

/** The Enhanced tab's menu: Leo's own layout, the templates (searchable), regenerating and a new template. */
export function TemplateMenu({
  enhanced,
  templates,
  value,
  generating,
  onPick,
  onRegenerate,
  onNewTemplate,
}: TemplateMenuProps) {
  const t = useTranslations("notesTemplates");
  return (
    <Command filter={containsQuery}>
      <CommandInput placeholder={t("menu.search")} />
      <CommandList>
        <CommandEmpty>{t("menu.noMatch")}</CommandEmpty>
        <CommandGroup>
          <TemplateItem template={enhanced} checked={value.id === enhanced.id} onSelect={onPick} />
        </CommandGroup>
        <CommandGroup heading={t("menu.heading")}>
          {templates.map((template) => (
            <TemplateItem key={template.id} template={template} checked={template.id === value.id} onSelect={onPick} />
          ))}
        </CommandGroup>
        <CommandSeparator alwaysRender />
        <CommandGroup forceMount>
          <CommandItem forceMount value="regenerate" disabled={generating} onSelect={onRegenerate}>
            <RefreshCw />
            {t("menu.regenerate")}
          </CommandItem>
          <CommandItem forceMount value="new-template" onSelect={onNewTemplate}>
            <Plus />
            {t("menu.newTemplate")}
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </Command>
  );
}

interface TemplateItemProps {
  readonly template: NoteTemplate;
  readonly checked: boolean;
  readonly onSelect: (template: NoteTemplate) => void;
}

function TemplateItem({ template, checked, onSelect }: TemplateItemProps) {
  const Icon = TEMPLATE_ICON_GLYPHS[template.icon];
  return (
    <CommandItem
      value={template.id}
      keywords={[template.name, template.description]}
      data-checked={checked}
      onSelect={() => onSelect(template)}
      title={template.description}
    >
      <Icon className="text-muted-foreground" />
      {/* A template the user made is named in whatever language they typed. */}
      <span dir="auto" className="truncate">
        {template.name}
      </span>
    </CommandItem>
  );
}
