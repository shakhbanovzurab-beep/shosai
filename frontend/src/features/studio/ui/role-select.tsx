"use client";

import { useTranslations } from "next-intl";

import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

import type { StudioRole } from "../domain/contract";
import { PROMPT_ROLES } from "../domain/roles";

type RoleSelectProps = { id: string; value: StudioRole; onChange: (role: StudioRole) => void };

export function RoleSelect({ id, value, onChange }: RoleSelectProps) {
  const t = useTranslations("studio");
  return (
    <Select
      value={value}
      onValueChange={(next) => {
        const role = PROMPT_ROLES.find((r) => r.id === next);
        if (role) onChange(role.id);
      }}
    >
      <SelectTrigger id={id} className="w-full">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          {PROMPT_ROLES.map((role) => (
            <SelectItem key={role.id} value={role.id}>
              {t(`roles.${role.id}.name`)}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  );
}
