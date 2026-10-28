import { Blocks, CalendarDays, Cloud, Hash, KeyRound, type LucideIcon, Mail } from "lucide-react";
import {
  type SimpleIcon as Brand,
  siConfluence,
  siDropbox,
  siGithub,
  siGitlab,
  siGmail,
  siGooglecalendar,
  siGoogledrive,
  siHubspot,
  siJira,
  siMaildotru,
  siNotion,
  siZapier,
} from "simple-icons";

import { SimpleIcon } from "@/components/simple-icon";

// simple-icons has no Microsoft, Slack, Yandex, CalDAV, Attio or Affinity marks, so those use neutral glyphs.
const LOGOS: Record<string, Brand | LucideIcon> = {
  gmail: siGmail,
  google_calendar: siGooglecalendar,
  outlook: Mail,
  outlook_calendar: CalendarDays,
  yandex_mail: Mail,
  yandex_calendar: CalendarDays,
  mailru_mail: siMaildotru,
  caldav: CalendarDays,
  google_drive: siGoogledrive,
  dropbox: siDropbox,
  yandex_disk: Cloud,
  notion: siNotion,
  confluence: siConfluence,
  slack: Hash,
  github: siGithub,
  gitlab: siGitlab,
  jira: siJira,
  hubspot: siHubspot,
  affinity: KeyRound,
  zapier: siZapier,
};

/** The app's mark in a small tile, like Claude's connector list; unknown apps get a generic glyph. */
export function ConnectorLogo({ id }: { id: string }) {
  const logo = LOGOS[id] ?? Blocks;
  const Glyph = "path" in logo ? null : logo;
  return (
    <span className="grid size-8 shrink-0 place-items-center rounded-lg border bg-background shadow-xs">
      {Glyph ? (
        <Glyph className="size-4" aria-hidden="true" />
      ) : (
        <SimpleIcon icon={logo as Brand} className="size-4" aria-hidden="true" />
      )}
    </span>
  );
}
