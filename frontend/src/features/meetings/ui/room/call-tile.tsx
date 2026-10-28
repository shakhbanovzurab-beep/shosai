import { cn } from "cn";
import { Hand, MicOff, Pin, PinOff } from "lucide-react";
import { useTranslations } from "use-intl";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";

import { type CallPerson, initialsOf } from "../../domain/call";
import type { CallSession, VideoKind } from "../../domain/call-session";

/** Что показывает плитка: экран важнее камеры; null — аватар. */
function videoOf(person: CallPerson): VideoKind | null {
  if (person.screenOn) return "screen";
  return person.cameraOn ? "camera" : null;
}

type CallTileProps = { person: CallPerson; session: CallSession; pinned: boolean; onPin: () => void };

/** Плитка сцены: видео (экран важнее камеры) или аватар, имя, выключенный микрофон, рука, закрепление. */
export function CallTile({ person, session, pinned, onPin }: CallTileProps) {
  const t = useTranslations("meetingRoom");
  const kind = videoOf(person);
  const mirrored = person.isLocal && kind === "camera";
  const name = person.isLocal ? t("people.you", { name: person.name }) : person.name;
  return (
    <figure
      className={cn(
        "group relative flex min-h-0 items-center justify-center overflow-hidden rounded-xl bg-muted ring-2 ring-transparent transition-shadow",
        person.speaking && "ring-primary",
      )}
    >
      {kind ? (
        <video
          ref={(element) => session.attach(person.identity, kind, element)}
          autoPlay
          playsInline
          muted={person.isLocal}
          className={cn("size-full", kind === "screen" ? "object-contain" : "object-cover", mirrored && "-scale-x-100")}
        >
          {/* Живое видео звонка без субтитров: речь участников расшифровывает Leo в заметках. */}
          <track kind="captions" />
        </video>
      ) : (
        <Avatar className="size-20 text-2xl">
          <AvatarFallback>{initialsOf(person.name)}</AvatarFallback>
        </Avatar>
      )}
      {person.hand ? (
        <span className="absolute start-2 top-2 flex items-center gap-1 rounded-md bg-background/90 px-2 py-1 text-xs">
          <Hand aria-hidden="true" className="size-3.5" />
          {t("people.handRaised")}
        </span>
      ) : null}
      <Button
        variant="secondary"
        size="icon-sm"
        aria-pressed={pinned}
        aria-label={t(pinned ? "people.unpin" : "people.pin", { name: person.name })}
        onClick={onPin}
        className="absolute end-2 top-2 opacity-0 transition-opacity focus-visible:opacity-100 group-hover:opacity-100 aria-pressed:opacity-100 pointer-coarse:opacity-100"
      >
        {pinned ? <PinOff aria-hidden="true" /> : <Pin aria-hidden="true" />}
      </Button>
      <figcaption className="absolute start-2 bottom-2 flex max-w-[calc(100%-1rem)] items-center gap-1.5 rounded-md bg-background/90 px-2 py-1 text-xs">
        {person.micOn ? null : <MicOff aria-label={t("people.muted")} className="size-3.5 shrink-0" />}
        <span dir="auto" className="truncate">
          {name}
        </span>
      </figcaption>
    </figure>
  );
}
