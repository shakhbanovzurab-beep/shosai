"use client";

import { useTranslations } from "use-intl";

import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";

import type { Skill } from "../domain/contract";

/** The installed skills a prompt can use, as checkboxes; their names and descriptions are as their authors wrote them. */
export function SkillPicker({
  skills,
  value,
  onChange,
}: {
  skills: Skill[];
  value: string[];
  onChange: (ids: string[]) => void;
}) {
  const t = useTranslations("studioPrompts");
  if (skills.length === 0) {
    return <p className="text-muted-foreground text-sm">{t("editor.noSkills")}</p>;
  }
  const selected = new Set(value);
  return (
    <ul className="flex max-h-44 flex-col gap-1 overflow-y-auto rounded-lg border p-2">
      {skills.map((skill) => {
        const id = `skill-${skill.id}`;
        const checked = selected.has(skill.id);
        return (
          <li key={skill.id} className="flex items-start gap-2 rounded-md p-1.5 hover:bg-muted/50">
            <Checkbox
              id={id}
              checked={checked}
              onCheckedChange={(next) =>
                onChange(next === true ? [...value, skill.id] : value.filter((skillId) => skillId !== skill.id))
              }
              className="mt-0.5"
            />
            <Label htmlFor={id} className="flex min-w-0 flex-col items-start gap-0.5 font-normal">
              <span dir="auto" className="font-mono text-sm">
                {skill.name}
              </span>
              <span dir="auto" className="line-clamp-1 text-muted-foreground text-xs">
                {skill.description}
              </span>
            </Label>
          </li>
        );
      })}
    </ul>
  );
}
