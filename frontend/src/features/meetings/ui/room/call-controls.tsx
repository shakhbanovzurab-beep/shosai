import { Hand, MessageSquare, Mic, MicOff, MonitorUp, PenLine, Users, Video, VideoOff } from "lucide-react";
import { useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";
import { Toggle } from "@/components/ui/toggle";

import type { CallPerson, CallRole } from "../../domain/call";
import type { CallPanelKind } from "./call-panel";
import { InviteDialog } from "./invite-dialog";
import { LeaveMenu } from "./leave-menu";
import { ReactionPicker } from "./reaction-picker";

type CallControlsProps = {
  self: CallPerson;
  role: CallRole;
  link: string;
  people: number;
  unread: number;
  panel: CallPanelKind | null;
  onMic: (on: boolean) => void;
  onCamera: (on: boolean) => void;
  onScreen: (on: boolean) => void;
  onHand: (raised: boolean) => void;
  onReact: (emoji: string) => boolean;
  onPanel: (panel: CallPanelKind | null) => void;
  /** Открыта ли доска; null — у звонка доски нет. */
  board: boolean | null;
  onBoard: (open: boolean) => void;
  onLeave: () => void;
  onEndForAll: () => void;
};

/** Панель звонка: свои микрофон, камера, экран и рука, реакции, чат, участники, приглашение и выход. */
export function CallControls(props: CallControlsProps) {
  const t = useTranslations("meetingRoom");
  const { self, panel } = props;
  const togglePanel = (kind: CallPanelKind) => props.onPanel(panel === kind ? null : kind);
  return (
    <nav aria-label={t("controls.label")} className="flex flex-wrap items-center justify-center gap-2 px-3 py-3">
      <Toggle variant="outline" pressed={self.micOn} onPressedChange={props.onMic} aria-label={t("controls.mic")}>
        {self.micOn ? <Mic aria-hidden="true" /> : <MicOff aria-hidden="true" />}
      </Toggle>
      <Toggle
        variant="outline"
        pressed={self.cameraOn}
        onPressedChange={props.onCamera}
        aria-label={t("controls.camera")}
      >
        {self.cameraOn ? <Video aria-hidden="true" /> : <VideoOff aria-hidden="true" />}
      </Toggle>
      <Toggle
        variant="outline"
        pressed={self.screenOn}
        onPressedChange={props.onScreen}
        aria-label={t("controls.screen")}
      >
        <MonitorUp aria-hidden="true" />
      </Toggle>
      <Toggle
        variant="outline"
        pressed={self.hand !== null}
        onPressedChange={props.onHand}
        aria-label={t("controls.hand")}
      >
        <Hand aria-hidden="true" />
      </Toggle>
      <ReactionPicker onReact={props.onReact} />
      {props.board === null ? null : (
        <Toggle
          variant="outline"
          pressed={props.board}
          onPressedChange={props.onBoard}
          aria-label={t("controls.board")}
        >
          <PenLine aria-hidden="true" />
        </Toggle>
      )}
      <Toggle
        variant="outline"
        pressed={panel === "chat"}
        onPressedChange={() => togglePanel("chat")}
        aria-label={t("controls.chat")}
      >
        <MessageSquare aria-hidden="true" />
        {props.unread > 0 ? (
          <Badge className="h-5 min-w-5 px-1 tabular-nums">
            <span aria-hidden="true">{props.unread}</span>
            <span className="sr-only">{t("controls.unread", { count: props.unread })}</span>
          </Badge>
        ) : null}
      </Toggle>
      <Toggle
        variant="outline"
        pressed={panel === "people"}
        onPressedChange={() => togglePanel("people")}
        aria-label={t("controls.people")}
      >
        <Users aria-hidden="true" />
        <span className="tabular-nums">{props.people}</span>
      </Toggle>
      <InviteDialog link={props.link} />
      <LeaveMenu role={props.role} onLeave={props.onLeave} onEndForAll={props.onEndForAll} />
    </nav>
  );
}
