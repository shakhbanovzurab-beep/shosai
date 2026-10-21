"use client";

import { useState } from "react";

import { Check, UserRound, UserX } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Link } from "@/lib/navigation";

import type { Assignee, TaskSpace } from "../../domain/tasks-contract";
import { useBoardSelector } from "../../model/board-hooks";
import { OwnerAvatar } from "../task-owner";
import { useValueLabel } from "./value-label";

/** Имена, которые уже стоят исполнителями на этой доске, — для быстрого выбора. */
function useKnownNames(): string {
  // Строка, а не массив: выбор из хранилища должен возвращать неизменную ссылку, пока имена те же.
  return useBoardSelector((s) =>
    [...new Set(Object.values(s.cards).flatMap((card) => (card.assignee ? [card.assignee.name] : [])))]
      .toSorted()
      .join("\n"),
  );
}

/** Исполнитель задачи пространства: участник пространства; сменить — там (до API участников, tasks step 11). */
function WorkspaceAssignee({ assignee, space }: { assignee: Assignee | null; space: TaskSpace }) {
  const t = useTranslations("kanbanPanel");
  const tk = useTranslations("kanban");
  return (
    <>
      <span className="flex min-w-0 items-center gap-1.5 text-sm">
        <OwnerAvatar owner={assignee} />
        <span dir="auto" className="truncate">
          {assignee?.name ?? tk("card.unassigned")}
        </span>
      </span>
      <Button asChild variant="link" size="xs">
        <Link href={`/app/w/${encodeURIComponent(space.workspace_slug)}/tasks`}>
          {t("assignee.inWorkspace", { workspace: space.workspace_name })}
        </Link>
      </Button>
    </>
  );
}

/** Исполнитель личной задачи — имя, как его пишут: из уже знакомых на доске или новое. */
function PersonalAssignee({
  assignee,
  labelId,
  disabled,
  onChange,
}: {
  assignee: Assignee | null;
  labelId: string;
  disabled: boolean;
  onChange: (name: string | null) => void;
}) {
  const t = useTranslations("kanbanPanel");
  const tk = useTranslations("kanban");
  const valueLabel = useValueLabel(labelId);
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const known = useKnownNames().split("\n").filter(Boolean);
  const name = typed.trim();
  const pick = (next: string | null) => {
    setOpen(false);
    setTyped("");
    if (next !== (assignee?.name ?? null)) onChange(next);
  };
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" disabled={disabled} {...valueLabel} className="max-w-full font-normal">
          {assignee ? <OwnerAvatar owner={assignee} /> : <UserRound data-icon="inline-start" />}
          <span dir="auto" className="truncate">
            {assignee?.name ?? tk("card.unassigned")}
          </span>
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-72 p-0">
        <Command>
          <CommandInput value={typed} onValueChange={setTyped} placeholder={t("assignee.placeholder")} />
          <CommandList>
            <CommandEmpty>{t("assignee.noNames")}</CommandEmpty>
            <CommandGroup>
              {name && !known.includes(name) ? (
                <CommandItem value={`new:${name}`} onSelect={() => pick(name)}>
                  {t("assignee.assign", { name })}
                </CommandItem>
              ) : null}
              {known.map((person) => (
                <CommandItem key={person} value={person} onSelect={() => pick(person)}>
                  <Check className={person === assignee?.name ? undefined : "invisible"} />
                  <span dir="auto">{person}</span>
                </CommandItem>
              ))}
              {assignee ? (
                <CommandItem value="clear" onSelect={() => pick(null)}>
                  <UserX />
                  {t("assignee.clear")}
                </CommandItem>
              ) : null}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

/** Исполнитель: у задачи пространства — его участник, у личной — имя. */
export function AssigneeField(props: {
  assignee: Assignee | null;
  space: TaskSpace | null;
  labelId: string;
  disabled: boolean;
  onChange: (name: string | null) => void;
}) {
  return props.space ? (
    <WorkspaceAssignee assignee={props.assignee} space={props.space} />
  ) : (
    <PersonalAssignee {...props} />
  );
}
