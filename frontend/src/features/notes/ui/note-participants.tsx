"use client";

import { type FormEvent, useId, useState } from "react";

import { Users, X } from "lucide-react";
import { useTranslations } from "use-intl";

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
import { useMe } from "@/features/identity/model/session-store";
import { getInitials } from "@/lib/utils";

import { type AttendeeProblem, attendeeProblem, isOwnEmail } from "../domain/attendees";
import type { MeetingPage, MeetingParticipant } from "../domain/meeting-page";
import { addParticipant, removeParticipant } from "../model/participants";

const shownName = (person: MeetingParticipant) => person.name ?? person.email ?? "";

/** Сколько людей было на встрече, под заголовком; открывает список, куда можно добавить человека по адресу. */
export function NoteParticipants({ note }: { readonly note: MeetingPage }) {
  const t = useTranslations("notesNote");
  const notes = useTranslations("notes");
  const me = useMe();
  const people = note.participants;
  const words = { t, notes };

  return (
    <MetaItem label={notes("fields.participants")} className="shrink-0">
      <Popover>
        <PopoverTrigger asChild>
          <Button variant="ghost" size="xs" className={META_VALUE_BUTTON}>
            <Users className="size-4" aria-hidden="true" />
            <span className="tabular-nums" aria-hidden="true">
              {note.participantCount}
            </span>
            <span className="sr-only">{t("participants.count", { count: note.participantCount })}</span>
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-80">
          <PopoverHeader>
            <PopoverTitle>{notes("fields.participants")}</PopoverTitle>
            <PopoverDescription>{t("participants.inMeeting", { count: note.participantCount })}</PopoverDescription>
          </PopoverHeader>
          <ul className="flex max-h-64 flex-col gap-2.5 overflow-y-auto">
            {people.map((person) => (
              <li key={person.id} className="flex items-center gap-2.5">
                <Avatar size="sm">
                  <AvatarFallback>{getInitials(shownName(person))}</AvatarFallback>
                </Avatar>
                <div className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate text-sm">
                    {me && person.email && isOwnEmail(person.email, me.email) ? (
                      t("participants.you", { name: shownName(person) })
                    ) : (
                      <span dir="auto">{shownName(person)}</span>
                    )}
                  </span>
                  {person.name && person.email ? (
                    <span dir="auto" className="truncate text-muted-foreground text-xs">
                      {person.email}
                    </span>
                  ) : null}
                </div>
                {note.manageable && person.source === "added" ? (
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    aria-label={notes("remove", { name: shownName(person) })}
                    onClick={() => void removeParticipant(note.id, person, words)}
                  >
                    <X />
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
          {note.manageable ? (
            <AddParticipant attendees={people} onAdd={(email) => addParticipant(note.id, email, words)} />
          ) : null}
        </PopoverContent>
      </Popover>
    </MetaItem>
  );
}

function AddParticipant({
  attendees,
  onAdd,
}: {
  readonly attendees: readonly MeetingParticipant[];
  readonly onAdd: (email: string) => Promise<boolean>;
}) {
  const t = useTranslations("notesNote");
  const common = useTranslations("common");
  const [problem, setProblem] = useState<AttendeeProblem | null>(null);
  const [adding, setAdding] = useState(false);
  const errorId = useId();

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const email = String(new FormData(form).get("email") ?? "").trim();
    const found = attendeeProblem(email, attendees);
    setProblem(found);
    if (found) return;
    setAdding(true);
    const added = await onAdd(email);
    setAdding(false);
    if (added) form.reset();
  };

  return (
    <form onSubmit={(event) => void submit(event)} noValidate>
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
            <InputGroupButton type="submit" disabled={adding}>
              {common("actions.add")}
            </InputGroupButton>
          </InputGroupAddon>
        </InputGroup>
        {problem ? <FieldError id={errorId}>{t(`participants.${problem}`)}</FieldError> : null}
      </Field>
    </form>
  );
}
