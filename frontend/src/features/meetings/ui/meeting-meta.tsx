import { cn } from "cn";
import { MapPin, Mic, Upload, Users, Video } from "lucide-react";
import { siGooglemeet } from "simple-icons";
import { useFormatter, useTranslations } from "use-intl";

import { ShosaiMark } from "@/components/shosai-mark";
import { SimpleIcon } from "@/components/simple-icon";
import { Avatar, AvatarFallback, AvatarGroup, AvatarGroupCount } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { getInitials } from "@/lib/utils";

import type { Meeting, MeetingSource } from "../domain/meeting";

type CallService = Exclude<MeetingSource, "shosai" | "in_person" | "recording" | "upload">;

// The call services' own names, written the same in every language; Studio's words come from the catalog.
const SERVICE_NAMES: Record<CallService, string> = {
  google_meet: "Google Meet",
  zoom: "Zoom",
  teams: "Microsoft Teams",
};

const isCallService = (source: MeetingSource): source is CallService => source in SERVICE_NAMES;

// simple-icons has no Microsoft mark and only Zoom's wordmark, so those use neutral glyphs, as in Knowledge base.
function SourceIcon({ source }: { source: MeetingSource }) {
  const className = "size-3.5 shrink-0";
  if (source === "google_meet")
    return <SimpleIcon icon={siGooglemeet} aria-hidden="true" className={cn(className, "fill-current")} />;
  if (source === "zoom") return <Video className={className} aria-hidden="true" />;
  if (source === "teams") return <Users className={className} aria-hidden="true" />;
  if (source === "shosai") return <ShosaiMark className={className} />;
  if (source === "recording") return <Mic className={className} aria-hidden="true" />;
  if (source === "upload") return <Upload className={className} aria-hidden="true" />;
  return <MapPin className={className} aria-hidden="true" />;
}

/** Where the meeting happens: the call service, a Shosai room, the room for an in-person meeting, or how it was recorded. */
export function MeetingSourceLabel({ meeting }: { meeting: Pick<Meeting, "source" | "location"> }) {
  const t = useTranslations("meetings");
  const { source, location } = meeting;
  // The room of an in-person meeting is what someone typed into the invitation.
  const place = source === "in_person" && location ? location : null;
  const label = place ?? (isCallService(source) ? SERVICE_NAMES[source] : t(`source.${source}`));
  return (
    <span className="inline-flex min-w-0 items-center gap-1.5 text-muted-foreground">
      <SourceIcon source={source} />
      <span dir={place ? "auto" : undefined} className="truncate">
        {label}
      </span>
    </span>
  );
}

/** Up to `max` faces, then "+N"; the full list is in the accessible label and the tooltip. */
export function MeetingParticipants({ people, max = 4 }: { people: Meeting["participants"]; max?: number }) {
  const t = useTranslations("meetings");
  const format = useFormatter();
  const names = format.list(people.map((p) => p.name));
  const shown = people.slice(0, max);
  const hidden = people.length - shown.length;
  return (
    <AvatarGroup title={names} className="-space-x-1.5">
      <span className="sr-only">{t("participants", { names })}</span>
      {shown.map((person) => (
        <Avatar key={person.name} aria-hidden="true">
          <AvatarFallback className="text-[11px]">{getInitials(person.name)}</AvatarFallback>
        </Avatar>
      ))}
      {hidden > 0 ? (
        <AvatarGroupCount className="text-[11px]" aria-hidden="true">
          +{format.number(hidden)}
        </AvatarGroupCount>
      ) : null}
    </AvatarGroup>
  );
}

/** The red "Live" marker with a pulsing dot (still for reduced motion). */
export function LiveBadge({ className }: { className?: string }) {
  const t = useTranslations("meetings");
  return (
    <Badge variant="destructive" className={cn("gap-1.5", className)}>
      <span className="relative flex size-1.5" aria-hidden="true">
        <span className="absolute inline-flex size-full animate-ping rounded-full bg-destructive opacity-75 motion-reduce:hidden" />
        <span className="relative inline-flex size-1.5 rounded-full bg-destructive" />
      </span>
      {t("liveBadge")}
    </Badge>
  );
}
