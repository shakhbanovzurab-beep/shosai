"use client";

import { useActionState, useState } from "react";

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
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";

import { TEAM_COLORS, TEAM_DESCRIPTION_MAX, TEAM_NAME_MAX, type Team, type TeamColor } from "../../domain/contract";
import { saveTeam } from "../../model/group-actions";
import { useWorkspace } from "../../model/use-workspace";
import { PersonAvatar } from "../shared/people";
import { TEAM_DOT_CLASSES } from "../shared/team-colors";

/** Mounted per opening: a new team starts with the admin in it, an existing one with its members. */
function TeamForm({ team, onDone }: { team: Team | null; onDone: () => void }) {
  const t = useTranslations("workspaceMembers");
  const shared = useTranslations("workspace");
  const common = useTranslations("common");
  const { ws, state } = useWorkspace();
  const [name, setName] = useState(team?.name ?? "");
  const [description, setDescription] = useState(team?.description ?? "");
  const [color, setColor] = useState<TeamColor>(
    team?.color ?? TEAM_COLORS[state.teams.length % TEAM_COLORS.length] ?? "blue",
  );
  const [isPrivate, setPrivate] = useState(team?.private ?? false);
  const [memberIds, setMemberIds] = useState(() =>
    team ? state.members.filter((m) => m.team_ids.includes(team.id)).map((m) => m.id) : [state.me_id],
  );
  const [error, setError] = useState<string | null>(null);
  const chosen = new Set(memberIds);

  const [, submit, pending] = useActionState(async () => {
    if (!name.trim()) {
      setError(t("teamForm.nameRequired"));
      return null;
    }
    const input = { name: name.trim(), description: description.trim(), color, private: isPrivate };
    const failure = await saveTeam(ws, team?.id ?? null, { ...input, member_ids: memberIds }, t);
    if (failure) setError(failure);
    else onDone();
    return null;
  }, null);

  return (
    <form action={submit} noValidate className="flex flex-col gap-4">
      <DialogHeader>
        <DialogTitle>{team ? t("teamForm.editTitle", { name: team.name }) : t("teams.new")}</DialogTitle>
        <DialogDescription>{t("teamForm.description")}</DialogDescription>
      </DialogHeader>
      <FieldGroup>
        <Field data-invalid={error ? true : undefined}>
          <FieldLabel htmlFor="team-name">{common("fields.name")}</FieldLabel>
          <Input
            id="team-name"
            value={name}
            onChange={(event) => {
              setName(event.target.value);
              setError(null);
            }}
            maxLength={TEAM_NAME_MAX}
            placeholder={t("teamForm.namePlaceholder")}
            dir="auto"
            autoComplete="off"
            aria-invalid={error ? true : undefined}
          />
          {error ? <FieldError role="alert">{error}</FieldError> : null}
        </Field>
        <Field>
          <FieldLabel htmlFor="team-description">{t("teamForm.descriptionLabel")}</FieldLabel>
          <Input
            id="team-description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            maxLength={TEAM_DESCRIPTION_MAX}
            placeholder={t("teamForm.descriptionPlaceholder")}
            dir="auto"
            autoComplete="off"
          />
        </Field>
        <FieldSet>
          <FieldLegend variant="label">{t("teamForm.color")}</FieldLegend>
          <div className="flex gap-2">
            {TEAM_COLORS.map((value) => (
              <button
                key={value}
                type="button"
                aria-pressed={color === value}
                aria-label={t(`teamForm.colors.${value}`)}
                title={t(`teamForm.colors.${value}`)}
                onClick={() => setColor(value)}
                className={cn(
                  "grid size-8 cursor-pointer place-items-center rounded-full border outline-none transition-colors focus-visible:ring-3 focus-visible:ring-ring/50",
                  color === value ? "border-foreground" : "hover:bg-muted",
                )}
              >
                <span aria-hidden="true" className={cn("size-4 rounded-full", TEAM_DOT_CLASSES[value])} />
              </button>
            ))}
          </div>
        </FieldSet>
        <Field orientation="horizontal">
          <FieldContent>
            <FieldLabel htmlFor="team-private">{shared("teams.private")}</FieldLabel>
            <FieldDescription>{t("teamForm.privateHint")}</FieldDescription>
          </FieldContent>
          <Switch id="team-private" checked={isPrivate} onCheckedChange={setPrivate} />
        </Field>
        <FieldSet>
          <FieldLegend variant="label">{t("membersCount", { count: memberIds.length })}</FieldLegend>
          <div className="flex max-h-52 flex-col overflow-y-auto rounded-lg border p-1">
            {state.members.map((member) => (
              <Label
                key={member.id}
                className="flex items-center gap-2.5 rounded-md px-2 py-1.5 font-normal hover:bg-muted"
              >
                <Checkbox
                  checked={chosen.has(member.id)}
                  onCheckedChange={(on) =>
                    setMemberIds(on === true ? [...memberIds, member.id] : memberIds.filter((id) => id !== member.id))
                  }
                />
                <PersonAvatar name={member.name} className="size-5" />
                <span dir="auto" className="truncate">
                  {member.id === state.me_id ? shared("people.nameYou", { name: member.name }) : member.name}
                </span>
              </Label>
            ))}
          </div>
        </FieldSet>
      </FieldGroup>
      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onDone}>
          {common("actions.cancel")}
        </Button>
        <Button type="submit" disabled={pending}>
          {pending ? <Spinner data-icon="inline-start" /> : null}
          {team ? common("actions.save") : t("teamForm.create")}
        </Button>
      </DialogFooter>
    </form>
  );
}

export function TeamDialog({
  team,
  open,
  onOpenChange,
}: {
  team: Team | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        {open ? <TeamForm team={team} onDone={() => onOpenChange(false)} /> : null}
      </DialogContent>
    </Dialog>
  );
}
