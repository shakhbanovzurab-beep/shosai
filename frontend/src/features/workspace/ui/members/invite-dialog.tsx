"use client";

import { useActionState, useState } from "react";

import Link from "next/link";

import { useFormatter, useTranslations } from "next-intl";

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
import { Field, FieldGroup, FieldLegend, FieldSet } from "@/components/ui/field";
import { FieldDescription, FieldError, FieldLabel } from "@/components/ui/field-text";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";

import { type AssignableRole, INVITES_PER_REQUEST } from "../../domain/contract";
import { parseInviteEmails, seatUsage, visibleTeams } from "../../domain/people";
import { useInviteDialog } from "../../model/invite-dialog-store";
import { invitePeople } from "../../model/people-actions";
import { useWorkspace } from "../../model/use-workspace";
import { TeamDot } from "../shared/badges";
import { RoleSelect } from "./role-select";

/** Mounted per opening, so each invite starts empty. */
function InviteForm({ onDone }: { onDone: () => void }) {
  const t = useTranslations("workspaceMembers");
  const format = useFormatter();
  const { ws, state, can } = useWorkspace();
  const [text, setText] = useState("");
  const [role, setRole] = useState<AssignableRole>("member");
  const [teamIds, setTeamIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const parsed = parseInviteEmails(text, state);
  const { left } = seatUsage(state);
  const teams = visibleTeams(state, can.me, can.admin);
  const over = parsed.emails.length > left;
  const chosen = new Set(teamIds);

  const count = parsed.emails.length;
  let hint = t("invite.hint", { left });
  if (count > 0)
    hint = over ? t("invite.overSeats", { count, left }) : t("invite.seatsAfter", { count, left: left - count });

  // The pending state comes from the action, so the button can't be pressed twice while it runs.
  const [, submit, pending] = useActionState(async () => {
    if (parsed.invalid.length > 0) setError(t("invite.checkEmails", { emails: format.list(parsed.invalid) }));
    else if (count === 0) setError(t(parsed.existing.length > 0 ? "invite.allExisting" : "invite.emailRequired"));
    else if (count > INVITES_PER_REQUEST) setError(t("invite.tooMany", { count: INVITES_PER_REQUEST }));
    else {
      const failure = await invitePeople(ws, { emails: parsed.emails, role, team_ids: teamIds }, t);
      if (failure) setError(failure);
      else onDone();
    }
    return null;
  }, null);

  return (
    <form action={submit} noValidate className="flex flex-col gap-4">
      <DialogHeader>
        <DialogTitle>{t("invite.title", { workspace: state.workspace.name })}</DialogTitle>
        <DialogDescription>{t("invite.description")}</DialogDescription>
      </DialogHeader>
      <FieldGroup>
        <Field data-invalid={error ? true : undefined}>
          <FieldLabel htmlFor="invite-emails">{t("invite.emails")}</FieldLabel>
          <Textarea
            id="invite-emails"
            value={text}
            onChange={(event) => {
              setText(event.target.value);
              setError(null);
            }}
            // i18n-ignore: example addresses, not words
            placeholder="maya@company.com, noah@company.com"
            dir="ltr"
            rows={3}
            autoFocus
            spellCheck={false}
            aria-invalid={error ? true : undefined}
          />
          {error ? <FieldError role="alert">{error}</FieldError> : <FieldDescription>{hint}</FieldDescription>}
          {parsed.existing.length > 0 && !error ? (
            <FieldDescription>{t("invite.skipped", { emails: format.list(parsed.existing) })}</FieldDescription>
          ) : null}
        </Field>
        <Field>
          <FieldLabel htmlFor="invite-role">{t("invite.role")}</FieldLabel>
          <RoleSelect id="invite-role" value={role} onChange={setRole} allowAdmin={can.admin} className="w-full" />
        </Field>
        {teams.length > 0 ? (
          <FieldSet>
            <FieldLegend variant="label">{t("invite.teams")}</FieldLegend>
            <div className="grid gap-2 sm:grid-cols-2">
              {teams.map((team) => (
                <Label key={team.id} className="flex items-center gap-2 font-normal">
                  <Checkbox
                    checked={chosen.has(team.id)}
                    onCheckedChange={(on) =>
                      setTeamIds(on === true ? [...teamIds, team.id] : teamIds.filter((id) => id !== team.id))
                    }
                  />
                  <TeamDot team={team} />
                  <span dir="auto">{team.name}</span>
                </Label>
              ))}
            </div>
          </FieldSet>
        ) : null}
      </FieldGroup>
      <DialogFooter>
        <div className="flex flex-col-reverse gap-2 sm:flex-row">
          {over && can.manageBilling ? (
            <Button asChild variant="outline">
              <Link href="/app/upgrade">{t("invite.addSeats")}</Link>
            </Button>
          ) : null}
          <Button type="submit" disabled={pending || over}>
            {pending ? <Spinner data-icon="inline-start" /> : null}
            {t("invite.send", { count: Math.max(1, count) })}
          </Button>
        </div>
      </DialogFooter>
    </form>
  );
}

/** The one invite dialog of the Team pages, opened through `openInviteDialog` from anywhere. */
export function InviteDialog() {
  const { can } = useWorkspace();
  const open = useInviteDialog((s) => s.open) && can.invite;
  const setOpen = useInviteDialog((s) => s.setOpen);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="sm:max-w-lg">
        {open ? <InviteForm onDone={() => setOpen(false)} /> : null}
      </DialogContent>
    </Dialog>
  );
}
