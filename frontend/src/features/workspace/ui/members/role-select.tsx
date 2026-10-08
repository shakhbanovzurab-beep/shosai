"use client";

import { useTranslations } from "use-intl";

import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

import { ASSIGNABLE_ROLES, type AssignableRole, type MemberRole } from "../../domain/contract";

const isAssignable = (value: string): value is AssignableRole => ASSIGNABLE_ROLES.some((r) => r === value);

/** A role picker where every option says in one line what the role can do. */
export function RoleSelect({
  id,
  value,
  onChange,
  allowAdmin = true,
  label,
  className,
}: {
  id?: string;
  value: AssignableRole;
  onChange: (role: AssignableRole) => void;
  allowAdmin?: boolean;
  label?: string;
  className?: string;
}) {
  const t = useTranslations("workspace");
  return (
    <Select
      value={value}
      onValueChange={(next) => {
        if (isAssignable(next)) onChange(next);
      }}
    >
      <SelectTrigger id={id} aria-label={label} className={className}>
        <SelectValue>{t(`roles.${value}.label`)}</SelectValue>
      </SelectTrigger>
      <SelectContent align="end" className="w-72">
        <SelectGroup>
          {(allowAdmin ? ASSIGNABLE_ROLES : ASSIGNABLE_ROLES.filter((role) => role !== "admin")).map((role) => (
            <SelectItem key={role} value={role} className="items-start py-2">
              <span className="flex flex-col gap-0.5">
                <span className="font-medium">{t(`roles.${role}.label`)}</span>
                <span className="text-muted-foreground text-xs">{t(`roles.${role}.description`)}</span>
              </span>
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  );
}

/** A role that can't be changed here, as plain text. */
export function RoleText({ role }: { role: MemberRole }) {
  const t = useTranslations("workspace");
  return <span className="w-28 px-2.5 text-muted-foreground text-sm">{t(`roles.${role}.label`)}</span>;
}
