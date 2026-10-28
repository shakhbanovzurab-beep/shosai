import { useState } from "react";

import { useTranslations } from "use-intl";

import { Spinner } from "@/components/ui/spinner";
import { useIsLg } from "@/hooks/use-lg";

import { type BroadcastSession, mayModerate, stageIsFull } from "../../domain/broadcast";
import { useBroadcastSnapshot } from "../../model/broadcast-session";
import { useCallSnapshot } from "../../model/call-session";
import { CallStage } from "../room/call-stage";
import { BroadcastChat } from "./broadcast-chat";
import { BroadcastHeader } from "./broadcast-header";
import { StageMembers } from "./stage-members";
import { HandQueue, WaitingQueue } from "./stage-queues";
import { StudioControls } from "./studio-controls";
import { StudioPanel, type StudioPanelKind } from "./studio-panel";

type StudioScreenProps = { session: BroadcastSession; link: string; onLeft: () => void };

/** Студия сцены: эфир глазами сцены, чат, руки и зал ожидания, сцена; ведущий начинает и заканчивает эфир. */
export function StudioScreen({ session, link, onLeft }: StudioScreenProps) {
  const t = useTranslations("meetingBroadcast");
  const broadcast = useBroadcastSnapshot(session);
  const call = useCallSnapshot(session.call);
  // Рядом со сценой чат открыт сразу; на узком экране шторка закрыла бы саму сцену.
  const wide = useIsLg();
  const [panel, setPanel] = useState<StudioPanelKind | null>(wide ? "chat" : null);
  const [pinned, setPinned] = useState<ReadonlySet<string>>(new Set());
  const self = call.people.find((person) => person.identity === call.self);
  if (!self)
    return (
      <div role="status" className="flex h-dvh items-center justify-center gap-2 bg-background text-sm">
        <Spinner />
        {t("connecting")}
      </div>
    );

  // На сцене — только её участники; поднятая рука трансляции — очередь зала, а не значок на плитке.
  const onStage = new Set(broadcast.members.map((member) => member.identity));
  const stage = call.people
    .filter((person) => person.isLocal || onStage.has(person.identity))
    .map((person) => ({ ...person, hand: null }));
  const moderates = mayModerate(broadcast.role);
  const tabs = [
    { kind: "chat" as const, count: 0, content: <BroadcastChat chat={broadcast.chat} onSend={session.sendChat} /> },
    ...(moderates
      ? [
          {
            kind: "hands" as const,
            count: broadcast.hands.length,
            content: (
              <HandQueue
                hands={broadcast.hands}
                stageFull={stageIsFull(broadcast.members)}
                onAnswer={session.answerHand}
              />
            ),
          },
        ]
      : []),
    ...(moderates && broadcast.waitingRoom
      ? [
          {
            kind: "waiting" as const,
            count: broadcast.admissions.length,
            content: <WaitingQueue admissions={broadcast.admissions} onAnswer={session.admit} />,
          },
        ]
      : []),
    {
      kind: "stage" as const,
      count: 0,
      content: <StageMembers members={broadcast.members} self={call.self} role={broadcast.role} session={session} />,
    },
  ];
  const togglePin = (identity: string) =>
    setPinned((current) => {
      const next = new Set(current);
      if (!next.delete(identity)) next.add(identity);
      return next;
    });

  return (
    <div className="flex h-dvh flex-col bg-background">
      <BroadcastHeader broadcast={broadcast} />
      {broadcast.status === "scheduled" ? (
        <p role="status" className="mx-3 mb-2 rounded-lg bg-muted px-3 py-2 text-sm">
          {t("studio.notLiveHint")}
        </p>
      ) : null}
      <main className="flex min-h-0 flex-1 gap-3 px-3">
        <CallStage
          people={stage}
          session={session.call}
          pinned={pinned}
          onPin={togglePin}
          onShowPeople={() => setPanel("stage")}
        />
        <StudioPanel panel={panel} onPanel={setPanel} tabs={tabs} />
      </main>
      <StudioControls
        self={self}
        status={broadcast.status}
        host={broadcast.role === "host"}
        link={link}
        waiting={moderates ? broadcast.hands.length + broadcast.admissions.length : 0}
        panelOpen={panel !== null}
        onMic={session.call.setMic}
        onCamera={session.call.setCamera}
        onScreen={(on) => void session.call.setScreen(on)}
        onPanel={(open) => setPanel(open ? "chat" : null)}
        onStart={() => void session.start()}
        onEnd={() => void session.end()}
        onLeave={() => {
          session.leave();
          onLeft();
        }}
      />
    </div>
  );
}
