import { Check, Hand, X } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";

import type { Admission, HandRequest } from "../../domain/broadcast";
import { initialsOf } from "../../domain/call";

type QueueRow = { id: string; name: string; at: string };

type QueueProps = {
  rows: QueueRow[];
  empty: string;
  accept: string;
  decline: string;
  acceptDisabled: boolean;
  onAnswer: (id: string, yes: boolean) => void;
};

/** Очередь зала: кто и когда, впустить или отказать. */
function Queue({ rows, empty, accept, decline, acceptDisabled, onAnswer }: QueueProps) {
  const format = useFormatter();
  if (rows.length === 0) return <p className="py-8 text-center text-muted-foreground text-sm">{empty}</p>;
  return (
    <ul className="flex flex-col gap-2 overflow-y-auto">
      {rows.map((row) => (
        <li key={row.id} className="flex items-center gap-2">
          <Avatar className="size-8">
            <AvatarFallback>{initialsOf(row.name)}</AvatarFallback>
          </Avatar>
          <div className="flex min-w-0 flex-1 flex-col">
            <span dir="auto" className="truncate text-sm">
              {row.name}
            </span>
            <time dateTime={row.at} className="text-muted-foreground text-xs tabular-nums">
              {format.dateTime(new Date(row.at), { hour: "numeric", minute: "2-digit" })}
            </time>
          </div>
          <Button
            size="icon-sm"
            variant="outline"
            aria-label={`${accept}: ${row.name}`}
            disabled={acceptDisabled}
            onClick={() => onAnswer(row.id, true)}
          >
            <Check aria-hidden="true" />
          </Button>
          <Button
            size="icon-sm"
            variant="ghost"
            aria-label={`${decline}: ${row.name}`}
            onClick={() => onAnswer(row.id, false)}
          >
            <X aria-hidden="true" />
          </Button>
        </li>
      ))}
    </ul>
  );
}

type HandsProps = { hands: HandRequest[]; stageFull: boolean; onAnswer: (id: string, invite: boolean) => void };

/** Поднятые руки зала: позвать на сцену или отклонить; на полную сцену не позвать. */
export function HandQueue({ hands, stageFull, onAnswer }: HandsProps) {
  const t = useTranslations("meetingBroadcast");
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      {stageFull ? (
        <p role="status" className="flex items-center gap-2 rounded-lg bg-muted px-3 py-2 text-sm">
          <Hand aria-hidden="true" className="size-4" />
          {t("hands.stageFull")}
        </p>
      ) : null}
      <Queue
        rows={hands}
        empty={t("hands.empty")}
        accept={t("hands.invite")}
        decline={t("hands.decline")}
        acceptDisabled={stageFull}
        onAnswer={onAnswer}
      />
    </div>
  );
}

type WaitingProps = { admissions: Admission[]; onAnswer: (id: string, admitted: boolean) => void };

/** Зал ожидания: зрители, которых ещё не впустили. */
export function WaitingQueue({ admissions, onAnswer }: WaitingProps) {
  const t = useTranslations("meetingBroadcast");
  return (
    <Queue
      rows={admissions}
      empty={t("waiting.empty")}
      accept={t("waiting.admit")}
      decline={t("waiting.deny")}
      acceptDisabled={false}
      onAnswer={onAnswer}
    />
  );
}
