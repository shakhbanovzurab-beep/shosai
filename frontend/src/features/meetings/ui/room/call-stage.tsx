import { cn } from "cn";
import { useTranslations } from "use-intl";

import { Avatar, AvatarFallback, AvatarGroup, AvatarGroupCount } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";

import { type CallPerson, initialsOf, stageOf } from "../../domain/call";
import type { CallSession } from "../../domain/call-session";
import { CallTile } from "./call-tile";

const GRID: Record<number, string> = {
  1: "grid-cols-1",
  2: "grid-cols-1 sm:grid-cols-2",
  3: "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3",
  4: "grid-cols-2",
};
const AVATARS_SHOWN = 8;

type CallStageProps = {
  people: CallPerson[];
  session: CallSession;
  pinned: ReadonlySet<string>;
  onPin: (identity: string) => void;
  onShowPeople: () => void;
};

/** Сцена: видео тех, кого слышно и кого закрепили (до шести), остальные — аватарами под ней (meetings §1.3). */
export function CallStage({ people, session, pinned, onPin, onShowPeople }: CallStageProps) {
  const t = useTranslations("meetingRoom");
  const { tiles, others } = stageOf(people, pinned);
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className={cn("grid min-h-0 flex-1 auto-rows-fr gap-3", GRID[tiles.length] ?? "grid-cols-2 lg:grid-cols-3")}>
        {tiles.map((person) => (
          <CallTile
            key={person.identity}
            person={person}
            session={session}
            pinned={pinned.has(person.identity)}
            onPin={() => onPin(person.identity)}
          />
        ))}
      </div>
      {others.length > 0 ? (
        <Button variant="ghost" className="h-auto self-center py-1.5" onClick={onShowPeople}>
          <AvatarGroup>
            {others.slice(0, AVATARS_SHOWN).map((person) => (
              <Avatar key={person.identity}>
                <AvatarFallback>{initialsOf(person.name)}</AvatarFallback>
              </Avatar>
            ))}
            {others.length > AVATARS_SHOWN ? (
              <AvatarGroupCount>+{others.length - AVATARS_SHOWN}</AvatarGroupCount>
            ) : null}
          </AvatarGroup>
          <span className="text-muted-foreground text-sm">{t("stage.others", { count: others.length })}</span>
        </Button>
      ) : null}
    </div>
  );
}
