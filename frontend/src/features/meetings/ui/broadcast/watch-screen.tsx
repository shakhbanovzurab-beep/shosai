import { useState } from "react";

import { Hand, LogOut, MessageSquare } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Toggle } from "@/components/ui/toggle";
import { useIsLg } from "@/hooks/use-lg";

import { type BroadcastSession, onAir, type StageMember } from "../../domain/broadcast";
import type { CallPerson } from "../../domain/call";
import { useBroadcastSnapshot } from "../../model/broadcast-session";
import { useCallSnapshot } from "../../model/call-session";
import { CallStage } from "../room/call-stage";
import { BroadcastChat } from "./broadcast-chat";
import { BroadcastHeader } from "./broadcast-header";
import { StudioPanel, type StudioPanelKind } from "./studio-panel";

// Человек сцены, чьей дорожки зритель ещё не получил: плитка с аватаром.
const personOf = (member: StageMember): CallPerson => ({
  identity: member.identity ?? member.principal,
  name: member.name,
  isLocal: false,
  isOwner: member.role === "host",
  micOn: true,
  cameraOn: false,
  screenOn: false,
  speaking: false,
  lastSpokeAt: 0,
  hand: null,
});

/** Эфир глазами зрителя: сцена в эфире, чат и поднятая рука; ведущий может позвать на сцену. */
export function WatchScreen({ session, onLeft }: { session: BroadcastSession; onLeft: () => void }) {
  const t = useTranslations("meetingBroadcast");
  const broadcast = useBroadcastSnapshot(session);
  const call = useCallSnapshot(session.call);
  // Рядом со сценой чат открыт сразу; на узком экране шторка закрыла бы саму сцену.
  const wide = useIsLg();
  const [panel, setPanel] = useState<StudioPanelKind | null>(wide ? "chat" : null);
  const [pinned, setPinned] = useState<ReadonlySet<string>>(new Set());
  const stage = onAir(broadcast.members).map((member) => {
    const person = call.people.find((item) => item.identity === member.identity);
    return person ? { ...person, hand: null } : personOf(member);
  });
  const chat = {
    kind: "chat" as const,
    count: 0,
    content: <BroadcastChat chat={broadcast.chat} onSend={(text) => session.sendChat(text)} />,
  };
  const togglePin = (identity: string) =>
    setPinned((current) => {
      const next = new Set(current);
      if (!next.delete(identity)) next.add(identity);
      return next;
    });

  return (
    <div className="flex h-dvh flex-col bg-background">
      <BroadcastHeader broadcast={broadcast} />
      {broadcast.hand === "invited" ? (
        <div
          role="alert"
          className="mx-3 mb-2 flex flex-wrap items-center gap-2 rounded-lg border bg-card px-3 py-2 text-sm"
        >
          <Hand aria-hidden="true" className="size-4" />
          <span className="me-auto">{t("watch.invited")}</span>
          <Button size="sm" onClick={() => void session.acceptInvite()}>
            {t("watch.accept")}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => void session.raiseHand(false)}>
            {t("watch.notNow")}
          </Button>
        </div>
      ) : null}
      {broadcast.hand === "raised" ? (
        <p role="status" className="mx-3 mb-2 rounded-lg bg-muted px-3 py-2 text-sm">
          {t("watch.handRaised")}
        </p>
      ) : null}
      <main className="flex min-h-0 flex-1 gap-3 px-3">
        {stage.length === 0 ? (
          <p className="flex flex-1 items-center justify-center rounded-xl border text-muted-foreground text-sm">
            {t("watch.emptyStage")}
          </p>
        ) : (
          <CallStage
            people={stage}
            session={session.call}
            pinned={pinned}
            onPin={togglePin}
            onShowPeople={() => undefined}
          />
        )}
        <StudioPanel panel={panel} onPanel={setPanel} tabs={[chat]} />
      </main>
      <nav aria-label={t("studio.controls")} className="flex flex-wrap items-center justify-center gap-2 px-3 py-3">
        <Toggle
          variant="outline"
          pressed={broadcast.hand !== "down"}
          onPressedChange={(raised) => void session.raiseHand(raised)}
          aria-label={t(broadcast.hand === "down" ? "watch.raiseHand" : "watch.lowerHand")}
        >
          <Hand aria-hidden="true" />
        </Toggle>
        <Toggle
          variant="outline"
          pressed={panel !== null}
          onPressedChange={(open) => setPanel(open ? "chat" : null)}
          aria-label={t("watch.chat")}
        >
          <MessageSquare aria-hidden="true" />
        </Toggle>
        <Button
          variant="ghost"
          onClick={() => {
            session.leave();
            onLeft();
          }}
        >
          <LogOut data-icon="inline-start" className="rtl:-scale-x-100" />
          {t("watch.leave")}
        </Button>
      </nav>
    </div>
  );
}
