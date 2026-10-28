import { useState } from "react";

import { Hand, MicOff, UserX } from "lucide-react";
import { useTranslations } from "use-intl";

import { ConfirmDestructive } from "@/components/feedback";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";

import { type CallPerson, type CallRole, initialsOf, mayRemove, raisedHands } from "../../domain/call";

type CallPeopleProps = {
  people: CallPerson[];
  role: CallRole;
  onLowerHand: (person: CallPerson) => void;
  onRemove: (person: CallPerson) => void;
};

/** Участники: сначала поднятые руки по очереди, затем все; владелец опускает руки и удаляет людей. */
export function CallPeople({ people, role, onLowerHand, onRemove }: CallPeopleProps) {
  const t = useTranslations("meetingRoom");
  const [removing, setRemoving] = useState<CallPerson | null>(null);
  const hands = raisedHands(people);
  const row = (person: CallPerson, hand: boolean) => (
    <li key={`${hand ? "hand" : "all"}-${person.identity}`} className="flex items-center gap-2.5 py-1.5">
      <Avatar size="sm">
        <AvatarFallback>{initialsOf(person.name)}</AvatarFallback>
      </Avatar>
      <div className="flex min-w-0 flex-1 flex-col">
        <span dir="auto" className="truncate text-sm">
          {person.isLocal ? t("people.you", { name: person.name }) : person.name}
        </span>
        {person.isOwner ? <span className="text-muted-foreground text-xs">{t("people.host")}</span> : null}
      </div>
      {hand ? <Hand aria-label={t("people.handRaised")} className="size-4 text-primary" /> : null}
      {!hand && !person.micOn ? (
        <MicOff aria-label={t("people.muted")} className="size-4 text-muted-foreground" />
      ) : null}
      {hand && (role === "owner" || person.isLocal) ? (
        <Button variant="ghost" size="sm" onClick={() => onLowerHand(person)}>
          {t("people.lowerHand")}
        </Button>
      ) : null}
      {!hand && mayRemove(role, person) ? (
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={t("people.remove", { name: person.name })}
          onClick={() => setRemoving(person)}
        >
          <UserX aria-hidden="true" />
        </Button>
      ) : null}
    </li>
  );
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto overscroll-contain">
      {hands.length > 0 ? (
        <section aria-labelledby="hands-title">
          <h3 id="hands-title" className="font-medium text-muted-foreground text-xs">
            {t("people.hands", { count: hands.length })}
          </h3>
          <ul>{hands.map((person) => row(person, true))}</ul>
        </section>
      ) : null}
      <section aria-labelledby="everyone-title">
        <h3 id="everyone-title" className="font-medium text-muted-foreground text-xs">
          {t("people.everyone", { count: people.length })}
        </h3>
        <ul>{people.map((person) => row(person, false))}</ul>
      </section>
      <ConfirmDestructive
        open={removing !== null}
        title={t("people.removeTitle", { name: removing?.name ?? "" })}
        description={t("people.removeDescription")}
        confirmLabel={t("people.removeConfirm")}
        onConfirm={() => {
          if (removing) onRemove(removing);
          setRemoving(null);
        }}
        onCancel={() => setRemoving(null)}
      />
    </div>
  );
}
