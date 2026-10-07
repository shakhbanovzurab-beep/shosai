import { File, FileSpreadsheet, FileText, Globe, type LucideIcon, Presentation } from "lucide-react";
import { type SimpleIcon as Brand, siConfluence, siGoogledrive, siNotion } from "simple-icons";

import { SimpleIcon } from "@/components/simple-icon";

import type { KnowledgeKind } from "../../domain/knowledge-contract";

const ICONS: Record<KnowledgeKind, Brand | LucideIcon> = {
  pdf: FileText,
  doc: FileText,
  text: File,
  sheet: FileSpreadsheet,
  slides: Presentation,
  notion: siNotion,
  drive: siGoogledrive,
  confluence: siConfluence,
  web: Globe,
};

/** A file type's glyph, or a connected source's logo; in a small tile, or bare inline with `size="sm"`. */
export function KnowledgeIcon({ kind, size = "md" }: { kind: KnowledgeKind; size?: "sm" | "md" }) {
  const icon = ICONS[kind];
  let glyph: React.ReactNode;
  if ("path" in icon) {
    glyph = <SimpleIcon icon={icon} aria-hidden="true" className="size-4 fill-current text-muted-foreground" />;
  } else {
    const Glyph = icon;
    glyph = <Glyph className="size-4 text-muted-foreground" aria-hidden="true" />;
  }
  if (size === "sm") return glyph;
  return <span className="grid size-9 shrink-0 place-items-center rounded-lg border bg-muted">{glyph}</span>;
}
