import type { LucideIcon } from "lucide-react";
import { CircleHelp, Globe, Mic, MicOff, Monitor, ScreenShare, Smartphone, UserX, Video, VideoOff } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

import type { LiveKitParticipant, LiveKitTrack } from "../domain/contract";
import { deviceLabel } from "../domain/device";
import { formatTime } from "../domain/format";

const CLIENT_ICONS: Record<string, LucideIcon> = {
  desktop: Monitor,
  web: Globe,
  mobile: Smartphone,
};

const TRACKS: Record<LiveKitTrack["kind"], { label: string; on: LucideIcon; off: LucideIcon }> = {
  audio: { label: "Микрофон", on: Mic, off: MicOff },
  video: { label: "Камера", on: Video, off: VideoOff },
  screen: { label: "Экран", on: ScreenShare, off: ScreenShare },
};

function TrackChip({ track }: { track: LiveKitTrack }) {
  const meta = TRACKS[track.kind];
  const Icon = track.muted ? meta.off : meta.on;
  return (
    <li
      className={
        track.muted
          ? "inline-flex items-center gap-1 rounded-md bg-muted px-1.5 py-0.5 text-muted-foreground text-xs"
          : "inline-flex items-center gap-1 rounded-md bg-muted px-1.5 py-0.5 text-foreground text-xs"
      }
    >
      <Icon aria-hidden="true" className="size-3.5" />
      {track.muted ? `${meta.label} выкл.` : meta.label}
    </li>
  );
}

type ParticipantItemProps = {
  participant: LiveKitParticipant;
  removing: boolean;
  disabled: boolean;
  onRemove: () => void;
};

export function ParticipantItem({ participant, removing, disabled, onRemove }: ParticipantItemProps) {
  const DeviceIcon = (participant.device.client && CLIENT_ICONS[participant.device.client]) || CircleHelp;
  return (
    <li className="flex flex-col gap-2.5 rounded-lg border p-3">
      <div className="min-w-0">
        <div className="truncate font-medium">{participant.name}</div>
        <div className="truncate font-mono text-muted-foreground text-xs">{participant.identity}</div>
      </div>
      <div className="flex items-center gap-1.5 text-muted-foreground text-xs">
        <DeviceIcon aria-hidden="true" className="size-3.5 shrink-0" />
        <span className="min-w-0 truncate">{deviceLabel(participant.device)}</span>
      </div>
      {participant.tracks.length > 0 ? (
        <ul aria-label="Опубликованные треки" className="flex flex-wrap gap-1.5">
          {participant.tracks.map((track) => (
            <TrackChip key={track.sid} track={track} />
          ))}
        </ul>
      ) : (
        <p className="text-muted-foreground text-xs">Ничего не публикует</p>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-muted-foreground text-xs tabular-nums">
          Подключился в {formatTime(participant.joined_at)}
        </span>
        <Button variant="destructive" size="sm" onClick={onRemove} disabled={disabled}>
          {removing ? <Spinner aria-label="Отключаем" /> : <UserX aria-hidden="true" />}
          Отключить участника
        </Button>
      </div>
    </li>
  );
}
