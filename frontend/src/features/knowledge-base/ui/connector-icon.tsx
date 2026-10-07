import { cn } from "cn";
import { Cloud, Globe, Hash, type LucideIcon, Share2 } from "lucide-react";
import {
  type SimpleIcon as Brand,
  siConfluence,
  siDropbox,
  siGithub,
  siGitlab,
  siGoogledrive,
  siJira,
  siNotion,
  siObsidian,
} from "simple-icons";

import { SimpleIcon } from "@/components/simple-icon";

import type { ConnectorId } from "../domain/contract";

// simple-icons has no Slack, Microsoft or Yandex Disk marks, so those use neutral glyphs.
const ICONS: Record<ConnectorId, Brand | LucideIcon> = {
  slack: Hash,
  confluence: siConfluence,
  notion: siNotion,
  obsidian: siObsidian,
  jira: siJira,
  github: siGithub,
  gitlab: siGitlab,
  google_drive: siGoogledrive,
  sharepoint: Share2,
  dropbox: siDropbox,
  yandex_disk: Cloud,
  website: Globe,
};

export function ConnectorIcon({ id, className }: { id: ConnectorId; className?: string }) {
  const icon = ICONS[id];
  const Glyph = "path" in icon ? null : icon;
  return (
    <span className={cn("grid size-10 shrink-0 place-items-center rounded-lg border bg-muted", className)}>
      {Glyph ? (
        <Glyph className="size-5" aria-hidden="true" />
      ) : (
        <SimpleIcon icon={icon as Brand} className="size-5" aria-hidden="true" />
      )}
    </span>
  );
}
