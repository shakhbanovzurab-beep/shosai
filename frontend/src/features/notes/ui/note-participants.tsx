"use client";

import { type FormEvent, useId, useState } from "react";

import { Users, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";

import { META_VALUE_BUTTON, MetaItem } from "@/components/meta-item";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { FieldError } from "@/components/ui/field-text";
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from "@/components/ui/input-group";
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover";
import { getInitials } from "@/lib/utils";

import { ACCOUNT_EMAIL } from "../data/meeting-notes";
import { type AttendeeProblem, attendeeProblem, isOwnEmail, nameFromEmail } from "../domain/attendees";
import type { NoteParticipant } from "../domain/types";

/** How many people were in the meeting, under the title; opens the list, where more can be added by email. */
export function NoteParticipants({ participants }: { readonly participants: NoteParticipant[] }) {
  const t = useTranslations("notesNote");
  const notes = useTranslations("notes");
  // People added here, on top of the meeting's own. Local until notes have an API, like folder moves.
  const [added, setAdded] = useState<NoteParticipant[]>([]);
  const attendees = [...participants, ...added];
  const addedEmails = new Set(added.map((person) => person.email));

  const add = (email: string) => {
    setAdded((current) => [...current, { name: nameFromEmail(email), role: "", email }]);
    toast.success(t("participants.added", { email }));
  };

  return (
    <MetaItem label={notes("fields.participants")} className="shrink-0">
      <Popover>
        <PopoverTrigger asChild>
          <Button variant="ghost" size="xs" className={META_VALUE_BUTTON}>
            <Users className="size-4" aria-hidden="true" />
            <span className="tabular-nums" aria-hidden="true">
              {attendees.length}
            </span>
            <span className="sr-only">{t("participants.count", { count: attendees.length })}</span>
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-80">
          <PopoverHeader>
            <PopoverTitle>{notes("fields.participants")}</PopoverTitle>
            <PopoverDescription>{t("participants.inMeeting", { count: attendees.length })}</PopoverDescription>
          </PopoverHeader>
          <ul className="flex max-h-64 flex-col gap-2.5 overflow-y-auto">
            {attendees.map((person) => (
              <li key={person.email} className="flex items-center gap-2.5">
                <Avatar size="sm">
                  <AvatarFallback>{getInitials(person.name)}</AvatarFallback>
                </Avatar>
                <div className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate text-sm">
                    {isOwnEmail(person.email, ACCOUNT_EMAIL) ? (
                      t("participants.you", { name: person.name })
                    ) : (
                      <span dir="auto">{person.name}</span>
                    )}
                  </span>
                  <span dir="auto" className="truncate text-muted-foreground text-xs">
                    {person.role || person.email}
                  </span>
                </div>
                {addedEmails.has(person.email) ? (
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    aria-label={notes("remove", { name: person.name })}
                    onClick={() => setAdded((current) => current.filter((p) => p.email !== person.email))}
                  >
                    <X />
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
          <AddParticipant attendees={attendees} onAdd={add} />
        </PopoverContent>
      </Popover>
    </MetaItem>
  );
}

function AddParticipant({
  attendees,
  onAdd,
}: {
  readonly attendees: NoteParticipant[];
  readonly onAdd: (email: string) => void;
}) {
  const t = useTranslations("notesNote");
  const common = useTranslations("common");
  const [problem, setProblem] = useState<AttendeeProblem | null>(null);
  const errorId = useId();

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const email = String(new FormData(form).get("email") ?? "").trim();
    const found = attendeeProblem(email, attendees);
    setProblem(found);
    if (found) return;
    onAdd(email);
    form.reset();
  };

  return (
    <form onSubmit={submit} noValidate>
      <Field data-invalid={problem !== null || undefined}>
        <InputGroup>
          <InputGroupInput
            name="email"
            type="email"
            placeholder={t("participants.addPlaceholder")}
            autoComplete="off"
            spellCheck={false}
            aria-label={t("participants.addLabel")}
            aria-invalid={problem !== null || undefined}
            aria-describedby={problem ? errorId : undefined}
            onChange={() => setProblem(null)}
          />
          <InputGroupAddon align="inline-end">
            <InputGroupButton type="submit">{common("actions.add")}</InputGroupButton>
          </InputGroupAddon>
        </InputGroup>
        {problem ? <FieldError id={errorId}>{t(`participants.${problem}`)}</FieldError> : null}
      </Field>
    </form>
  );
}
