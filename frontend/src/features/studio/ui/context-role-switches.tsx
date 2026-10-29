"use client";

import { useTranslations } from "use-intl";

import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

import type { ContextRoles } from "../domain/contract";
import { type ContextRoleOption, isSwitchedOn, switched } from "../domain/context-roles";
import { ROLES } from "../domain/roles";
import { saveContextRoles } from "../model/save-actions";
import { useProblemWords } from "../model/use-problem-words";

const OPTIONS: ContextRoleOption[] = ["all", ...ROLES.map((role) => role.id)];

/** Шесть тумблеров: «Все» или роли, в чьи ответы подмешивается контекст; выбор сохраняется сразу. */
export function ContextRoleSwitches({ roles }: { roles: ContextRoles }) {
  const t = useTranslations("studio");
  const words = useProblemWords();

  return (
    <fieldset className="flex flex-col gap-2.5">
      <legend className="mb-2 font-medium text-muted-foreground text-xs uppercase tracking-wide">
        {t("preview.rolesLabel")}
      </legend>
      {OPTIONS.map((option) => {
        const id = `context-role-${option}`;
        const hint = option === "notes" ? t("preview.notesHint") : null;
        return (
          <div key={option} className="flex items-center justify-between gap-3">
            <div className="flex min-w-0 flex-col">
              <Label htmlFor={id} className="font-normal text-sm">
                {option === "all" ? t("preview.all") : t(`roles.${option}.name`)}
              </Label>
              {hint ? (
                <span id={`${id}-hint`} className="text-muted-foreground text-xs">
                  {hint}
                </span>
              ) : null}
            </div>
            <Switch
              id={id}
              checked={isSwitchedOn(roles, option)}
              aria-describedby={hint ? `${id}-hint` : undefined}
              onCheckedChange={(on) => void saveContextRoles(switched(roles, option, on), roles, words)}
            />
          </div>
        );
      })}
      <p className="mt-1 text-muted-foreground text-xs">{t("preview.leoNote")}</p>
    </fieldset>
  );
}
