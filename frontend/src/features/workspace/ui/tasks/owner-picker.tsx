"use client";

import { UserRound } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DropdownMenuLabel, DropdownMenuRadioGroup, DropdownMenuRadioItem } from "@/components/ui/dropdown-menu-items";

import type { Member } from "../../domain/contract";
import { PersonAvatar, PersonLabel } from "../shared/people";

const NOBODY = "nobody";

/** Who a task is assigned to; with `onChange` it opens the member list to hand it to someone else. */
export function OwnerPicker({
  owner,
  members,
  meId,
  onChange,
}: {
  owner: Member | null;
  members: Member[];
  meId: string;
  onChange?: (ownerId: string | null) => void;
}) {
  const t = useTranslations("workspaceTasks.owner");
  let name = t("unassigned");
  if (owner) name = owner.id === meId ? t("you") : owner.name;
  if (!onChange)
    return owner ? (
      <PersonLabel name={owner.name} label={name} className="text-sm" />
    ) : (
      <span className="text-muted-foreground text-sm">{name}</span>
    );

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="max-w-44 px-1.5" aria-label={t("change", { name })}>
          {owner ? (
            <PersonLabel name={owner.name} label={name} />
          ) : (
            <>
              <UserRound data-icon="inline-start" />
              <span className="text-muted-foreground">{t("unassigned")}</span>
            </>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="max-h-80 w-56 overflow-y-auto">
        <DropdownMenuLabel className="text-muted-foreground text-xs">{t("label")}</DropdownMenuLabel>
        <DropdownMenuGroup>
          <DropdownMenuRadioGroup
            value={owner?.id ?? NOBODY}
            onValueChange={(value) => onChange(value === NOBODY ? null : value)}
          >
            {members.map((member) => (
              <DropdownMenuRadioItem key={member.id} value={member.id}>
                <PersonAvatar name={member.name} className="size-5" />
                <span className="truncate" dir="auto">
                  {member.id === meId ? t("meOption", { name: member.name }) : member.name}
                </span>
              </DropdownMenuRadioItem>
            ))}
            <DropdownMenuRadioItem value={NOBODY}>
              <UserRound />
              {t("unassigned")}
            </DropdownMenuRadioItem>
          </DropdownMenuRadioGroup>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
