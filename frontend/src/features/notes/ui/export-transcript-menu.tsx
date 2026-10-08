"use client";

import { ChevronDown, Download } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DropdownMenuItem, DropdownMenuLabel, DropdownMenuShortcut } from "@/components/ui/dropdown-menu-items";

import { EXPORT_FORMATS } from "../domain/transcript-export";
import type { MeetingNote } from "../domain/types";
import { useTranscriptDownload } from "./use-transcript-download";

/** Export the transcript as text, Markdown, subtitles (SRT, VTT) or JSON. */
export function ExportTranscriptMenu({ note }: { readonly note: MeetingNote }) {
  const t = useTranslations("notesNote");
  const transcript = useTranscriptDownload();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm">
          <Download data-icon="inline-start" />
          {t("export.button")}
          <ChevronDown data-icon="inline-end" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="text-muted-foreground text-xs">{t("export.transcriptAs")}</DropdownMenuLabel>
        <DropdownMenuGroup>
          {EXPORT_FORMATS.map((format) => (
            <DropdownMenuItem key={format} onSelect={() => transcript.download(note, format)}>
              {transcript.formatName(format)}
              {/* A file extension reads left to right in every language. */}
              <DropdownMenuShortcut dir="ltr">.{format}</DropdownMenuShortcut>
            </DropdownMenuItem>
          ))}
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
