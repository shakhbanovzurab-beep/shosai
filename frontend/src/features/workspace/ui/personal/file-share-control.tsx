"use client";

import { useState } from "react";

import { ChevronDown, Share2 } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover";

import type { FileShare } from "../../domain/personal-contract";
import { useMyShares, useWorkspaces } from "../../model/resources";
import { type ShareableFile, ShareFileForm } from "./share-file-form";

/** Where each of the account's files is shared, by file id; empty until loaded. */
export function useSharedFiles(): Map<string, FileShare[]> {
  const shares = useMyShares();
  const byFile = new Map<string, FileShare[]>();
  if (shares.status !== "ready") return byFile;
  for (const share of shares.data.files) byFile.set(share.file_id, [...(byFile.get(share.file_id) ?? []), share]);
  return byFile;
}

/** "Share", or the workspaces a file is shared in; opens the form. Hidden without a workspace. */
export function FileShareControl({ file }: { file: ShareableFile }) {
  const [open, setOpen] = useState(false);
  const workspaces = useWorkspaces();
  const shared = useSharedFiles().get(file.id) ?? [];
  const t = useTranslations("workspacePersonal");
  const format = useFormatter();
  if (workspaces.status !== "ready" || workspaces.data.workspaces.length === 0) return null;
  const label =
    shared.length === 0
      ? t("share")
      : format.list(
          shared.map((s) => s.workspace.name),
          { type: "unit", style: "short" },
        );

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant={shared.length ? "outline" : "ghost"} size="sm" className="max-w-44">
          <Share2 data-icon="inline-start" />
          <span className="truncate" dir={shared.length ? "auto" : undefined}>
            {label}
          </span>
          <ChevronDown data-icon="inline-end" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80">
        <PopoverHeader>
          <PopoverTitle>{t("fileShare.title")}</PopoverTitle>
          <PopoverDescription>{t("fileShare.description")}</PopoverDescription>
        </PopoverHeader>
        <ShareFileForm file={file} onDone={() => setOpen(false)} />
      </PopoverContent>
    </Popover>
  );
}
