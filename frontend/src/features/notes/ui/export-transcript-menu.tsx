"use client";

import { ChevronDown, Download } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DropdownMenuItem, DropdownMenuLabel, DropdownMenuShortcut } from "@/components/ui/dropdown-menu-items";

import { EXPORT_FORMATS } from "../domain/transcript-export";
import { useTranscriptDownload } from "./use-transcript-download";

/** Выгрузка расшифровки текстом, Markdown, субтитрами (SRT, VTT) или JSON. */
export function ExportTranscriptMenu({ meetingId }: { readonly meetingId: string }) {
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
            <DropdownMenuItem key={format} onSelect={() => void transcript.downloadById(meetingId, format)}>
              {transcript.formatName(format)}
              {/* Расширение файла читается слева направо на любом языке. */}
              <DropdownMenuShortcut dir="ltr">.{format}</DropdownMenuShortcut>
            </DropdownMenuItem>
          ))}
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
