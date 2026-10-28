import { useEffect, useState } from "react";

import { useTranslations } from "use-intl";

import { Spinner } from "@/components/ui/spinner";

import type { CallSession } from "../../domain/call-session";
import { lastSeq, unreadCount } from "../../domain/chat-log";
import { isReaction } from "../../domain/reactions";
import { useCallSnapshot } from "../../model/call-session";
import type { LocalMedia } from "../../model/local-media";
import { BoardPanel } from "./board-panel";
import { CallChat } from "./call-chat";
import { CallControls } from "./call-controls";
import { CallDuration } from "./call-duration";
import { CallMarks } from "./call-marks";
import { CallPanel, type CallPanelKind } from "./call-panel";
import { CallPeople } from "./call-people";
import { CallStage } from "./call-stage";
import { ReactionsOverlay } from "./reactions-overlay";
import { RecordControl } from "./record-control";
import { CallEnded } from "./room-problem";
import { useRecordingNotice } from "./use-recording-notice";

type CallScreenProps = { session: CallSession; media: LocalMedia; onRejoin: () => void };

/** Звонок: сцена, панель чата и участников, реакции и управление; закрытая вкладка выходит из звонка. */
export function CallScreen({ session, media, onRejoin }: CallScreenProps) {
  const t = useTranslations("meetingRoom");
  const call = useCallSnapshot(session);
  const [panel, setPanel] = useState<CallPanelKind | null>(null);
  const [pinned, setPinned] = useState<ReadonlySet<string>>(new Set());
  const [readSeq, setReadSeq] = useState(0);
  const [boardOpen, setBoardOpen] = useState(false);
  const board = session.board?.() ?? null;
  useRecordingNotice(call.marks.recording, call.role === "owner");

  useEffect(() => {
    const leave = () => session.leave();
    window.addEventListener("pagehide", leave);
    return () => window.removeEventListener("pagehide", leave);
  }, [session]);

  const self = call.people.find((person) => person.identity === call.self);
  if (call.status === "ended") return <CallEnded end={call.end ?? "lost"} onRejoin={onRejoin} />;
  // Пока звонок не знает самого человека, он ещё подключается: это не обрыв.
  if (!self)
    return (
      <div role="status" className="flex h-dvh items-center justify-center gap-2 bg-background text-sm">
        <Spinner />
        {t("states.connecting")}
      </div>
    );

  const unread = panel === "chat" ? 0 : unreadCount(call.chat, readSeq, call.self);
  const openPanel = (next: CallPanelKind | null) => {
    // Прочитано всё, что было в чате, пока он был открыт.
    if (panel === "chat" || next === "chat") setReadSeq(lastSeq(call.chat));
    setPanel(next);
  };
  const togglePin = (identity: string) =>
    setPinned((current) => {
      const next = new Set(current);
      if (!next.delete(identity)) next.add(identity);
      return next;
    });

  return (
    <div className="flex h-dvh flex-col bg-background">
      <header className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2">
        <h1 dir="auto" className="truncate font-medium">
          {call.title ?? t("untitled")}
        </h1>
        <CallMarks marks={call.marks} />
        <span className="ms-auto flex items-center gap-3 text-muted-foreground text-sm tabular-nums">
          <CallDuration startedAt={call.startedAt} />
          <span>{t("header.people", { count: call.people.length })}</span>
        </span>
      </header>
      {call.status === "reconnecting" ? (
        <p role="status" className="mx-3 mb-2 flex items-center gap-2 rounded-lg bg-muted px-3 py-2 text-sm">
          <Spinner />
          {t("states.reconnecting")}
        </p>
      ) : null}
      <main className="relative flex min-h-0 flex-1 gap-3 px-3">
        {call.status === "connecting" ? (
          <div
            role="status"
            className="absolute inset-0 z-10 flex items-center justify-center gap-2 bg-background/80 text-sm"
          >
            <Spinner />
            {t("states.connecting")}
          </div>
        ) : null}
        {board && boardOpen ? (
          <BoardPanel board={board} onClose={() => setBoardOpen(false)} />
        ) : (
          <CallStage
            people={call.people}
            session={session}
            pinned={pinned}
            onPin={togglePin}
            onShowPeople={() => openPanel("people")}
          />
        )}
        <CallPanel
          panel={panel}
          onPanel={openPanel}
          chat={
            <CallChat
              chat={call.chat}
              self={call.self}
              notesOn={call.marks.notes}
              onSend={(text) => session.sendChat(text)}
            />
          }
          people={
            <CallPeople
              people={call.people}
              role={call.role}
              onLowerHand={(person) =>
                person.isLocal ? session.setHand(false) : void session.lowerHandOf(person.identity)
              }
              onRemove={(person) => void session.remove(person.identity)}
            />
          }
        />
        <ReactionsOverlay reactions={call.reactions} people={call.people} />
      </main>
      <CallControls
        self={self}
        role={call.role}
        link={call.link}
        people={call.people.length}
        unread={unread}
        panel={panel}
        onMic={(on) => {
          media.setMic(on);
          session.setMic(on);
        }}
        onCamera={(on) => {
          media.setCamera(on);
          session.setCamera(on);
        }}
        onScreen={(on) => void session.setScreen(on)}
        onHand={(raised) => session.setHand(raised)}
        onReact={(emoji) => isReaction(emoji) && session.react(emoji)}
        onPanel={openPanel}
        board={board ? boardOpen : null}
        onBoard={setBoardOpen}
        record={
          call.role === "owner" ? (
            <RecordControl recording={call.marks.recording} onRecording={(on) => session.setRecording(on)} />
          ) : null
        }
        onLeave={() => session.leave()}
        onEndForAll={() => void session.endForAll()}
      />
    </div>
  );
}
