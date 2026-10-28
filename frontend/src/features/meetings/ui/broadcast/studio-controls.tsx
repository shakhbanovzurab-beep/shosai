import { LogOut, MessageSquare, Mic, MicOff, MonitorUp, Radio, Video, VideoOff } from "lucide-react";
import { useTranslations } from "use-intl";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Toggle } from "@/components/ui/toggle";

import type { BroadcastStatus } from "../../domain/broadcast";
import type { CallPerson } from "../../domain/call";
import { InviteDialog } from "../room/invite-dialog";

type StudioControlsProps = {
  self: CallPerson;
  status: BroadcastStatus;
  /** Начинает и заканчивает эфир только ведущий. */
  host: boolean;
  link: string;
  waiting: number;
  panelOpen: boolean;
  onMic: (on: boolean) => void;
  onCamera: (on: boolean) => void;
  onScreen: (on: boolean) => void;
  onPanel: (open: boolean) => void;
  onStart: () => void;
  onEnd: () => void;
  onLeave: () => void;
};

/** Управление студией: свои устройства, панель зала, ссылка, начало и конец эфира, выход со сцены. */
export function StudioControls(props: StudioControlsProps) {
  const t = useTranslations("meetingBroadcast");
  const { self } = props;
  return (
    <nav aria-label={t("studio.controls")} className="flex flex-wrap items-center justify-center gap-2 px-3 py-3">
      <Toggle variant="outline" pressed={self.micOn} onPressedChange={props.onMic} aria-label={t("studio.mic")}>
        {self.micOn ? <Mic aria-hidden="true" /> : <MicOff aria-hidden="true" />}
      </Toggle>
      <Toggle
        variant="outline"
        pressed={self.cameraOn}
        onPressedChange={props.onCamera}
        aria-label={t("studio.camera")}
      >
        {self.cameraOn ? <Video aria-hidden="true" /> : <VideoOff aria-hidden="true" />}
      </Toggle>
      <Toggle
        variant="outline"
        pressed={self.screenOn}
        onPressedChange={props.onScreen}
        aria-label={t("studio.screen")}
      >
        <MonitorUp aria-hidden="true" />
      </Toggle>
      <Toggle
        variant="outline"
        pressed={props.panelOpen}
        onPressedChange={props.onPanel}
        aria-label={t("studio.panel")}
      >
        <MessageSquare aria-hidden="true" />
        {props.waiting > 0 ? <Badge className="h-5 min-w-5 px-1 tabular-nums">{props.waiting}</Badge> : null}
      </Toggle>
      <InviteDialog link={props.link} />
      {props.host && props.status === "scheduled" ? (
        <Button onClick={props.onStart}>
          <Radio data-icon="inline-start" />
          {t("studio.start")}
        </Button>
      ) : null}
      {props.host && props.status === "live" ? (
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant="destructive">{t("studio.end")}</Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{t("studio.endTitle")}</AlertDialogTitle>
              <AlertDialogDescription>{t("studio.endDescription")}</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{t("studio.cancel")}</AlertDialogCancel>
              <AlertDialogAction variant="destructive" onClick={props.onEnd}>
                {t("studio.end")}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      ) : null}
      <Button variant="ghost" onClick={props.onLeave}>
        <LogOut data-icon="inline-start" className="rtl:-scale-x-100" />
        {t("studio.leave")}
      </Button>
    </nav>
  );
}
