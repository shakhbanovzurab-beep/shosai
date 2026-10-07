import { Blocks, Cloud, Hash, type LucideIcon, Mail } from "lucide-react";
import {
  type SimpleIcon as Brand,
  siConfluence,
  siDropbox,
  siGithub,
  siGitlab,
  siGmail,
  siGoogledrive,
  siHubspot,
  siJira,
  siNotion,
} from "simple-icons";

import { SimpleIcon } from "@/components/simple-icon";

// simple-icons has no Microsoft, Slack or Yandex Disk marks, so those use neutral glyphs.
const LOGOS: Record<string, Brand | LucideIcon> = {
  gmail: siGmail,
  outlook: Mail,
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
