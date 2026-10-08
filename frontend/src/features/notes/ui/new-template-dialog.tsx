"use client";

import { type FormEvent, useRef, useState } from "react";

import { cn } from "cn";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { FieldError, FieldLabel } from "@/components/ui/field-text";
import { Input } from "@/components/ui/input";

import { type NoteTemplate, SECTION_KINDS, TEMPLATE_ICONS, type TemplateIcon } from "../domain/templates";
import { addTemplate } from "../model/templates-store";
import { TEMPLATE_ICON_GLYPHS } from "./template-icons";

const optionClass = (selected: boolean) =>
  cn(
    "cursor-pointer rounded-lg border outline-none transition-colors focus-visible:ring-3 focus-visible:ring-ring/50",
    selected ? "border-primary bg-primary/5" : "hover:bg-muted",
  );

/**
 * The form is mounted per opening, so every new template starts from the defaults: each section under its
 * usual heading in the interface language, which the user may rename. What they type is the template's own.
 */
function NewTemplateForm({ onDone, onCreated }: { onDone: () => void; onCreated: (template: NoteTemplate) => void }) {
  const t = useTranslations("notesTemplates");
  const common = useTranslations("common");
  const [icon, setIcon] = useState<TemplateIcon>("briefcase");
  const [sections, setSections] = useState(() =>
    SECTION_KINDS.map((kind) => ({ kind, title: t(`sections.${kind}`), included: true })),
  );
  const [problem, setProblem] = useState<"name" | "sections" | null>(null);
  const nameRef = useRef<HTMLInputElement>(null);

  const updateSection = (index: number, patch: Partial<(typeof sections)[number]>) =>
    setSections((current) => current.map((section, i) => (i === index ? { ...section, ...patch } : section)));

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const name = String(form.get("name") ?? "").trim();
    const included = sections.filter((section) => section.included);
    if (!name) {
      setProblem("name");
      nameRef.current?.focus();
      return;
    }
    if (included.length === 0) {
      setProblem("sections");
      return;
    }
    onDone();
    const template = {
      name,
      icon,
      description: String(form.get("description") ?? "").trim() || t("dialog.ownDescription"),
      sections: included.map(({ kind, title }) => ({ kind, title: title.trim() || t(`sections.${kind}`) })),
    };
    onCreated(addTemplate(template, t));
  };

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-5">
      <DialogHeader>
        <DialogTitle>{t("dialog.title")}</DialogTitle>
        <DialogDescription>{t("dialog.description")}</DialogDescription>
      </DialogHeader>
      <Field data-invalid={problem === "name" || undefined}>
        <FieldLabel htmlFor="template-name">{common("fields.name")}</FieldLabel>
        <Input
          ref={nameRef}
          id="template-name"
          name="name"
          dir="auto"
          maxLength={60}
          placeholder={t("dialog.namePlaceholder")}
          autoComplete="off"
          aria-invalid={problem === "name" || undefined}
          onChange={() => setProblem(null)}
        />
        {problem === "name" ? <FieldError>{t("dialog.nameRequired")}</FieldError> : null}
      </Field>
      <Field>
        <FieldLabel htmlFor="template-description">{t("dialog.descriptionLabel")}</FieldLabel>
        <Input
          id="template-description"
          name="description"
          dir="auto"
          maxLength={120}
          placeholder={t("dialog.descriptionPlaceholder")}
          autoComplete="off"
        />
      </Field>
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 font-medium text-sm">{t("dialog.icon")}</legend>
        <div className="grid grid-cols-5 gap-2">
          {TEMPLATE_ICONS.map((value) => {
            const Icon = TEMPLATE_ICON_GLYPHS[value];
            return (
              <button
                key={value}
                type="button"
                aria-pressed={icon === value}
                aria-label={t(`icons.${value}`)}
                title={t(`icons.${value}`)}
                onClick={() => setIcon(value)}
                className={cn("flex h-10 items-center justify-center", optionClass(icon === value))}
              >
                <Icon className="size-4" aria-hidden="true" />
              </button>
            );
          })}
        </div>
      </fieldset>
      <fieldset className="flex flex-col gap-2" data-invalid={problem === "sections" || undefined}>
        <legend className="mb-2 font-medium text-sm">{t("dialog.sections")}</legend>
        {sections.map((section, index) => (
          <div key={section.kind} className="flex items-center gap-3">
            <Checkbox
              checked={section.included}
              onCheckedChange={(checked) => {
                updateSection(index, { included: checked === true });
                setProblem(null);
              }}
              aria-label={t("dialog.include", { section: t(`sections.${section.kind}`) })}
            />
            <Input
              name={`section-${section.kind}`}
              dir="auto"
              value={section.title}
              onChange={(event) => updateSection(index, { title: event.target.value })}
              disabled={!section.included}
              maxLength={40}
              autoComplete="off"
              aria-label={t("dialog.heading", { section: t(`sections.${section.kind}`) })}
            />
          </div>
        ))}
        {problem === "sections" ? <FieldError>{t("dialog.sectionsRequired")}</FieldError> : null}
      </fieldset>
      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onDone}>
          {common("actions.cancel")}
        </Button>
        <Button type="submit">{t("dialog.create")}</Button>
      </DialogFooter>
    </form>
  );
}

interface NewTemplateDialogProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly onCreated: (template: NoteTemplate) => void;
}

export function NewTemplateDialog({ open, onOpenChange, onCreated }: NewTemplateDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        {open ? <NewTemplateForm onDone={() => onOpenChange(false)} onCreated={onCreated} /> : null}
      </DialogContent>
    </Dialog>
  );
}
