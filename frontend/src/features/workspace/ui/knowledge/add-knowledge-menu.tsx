"use client";

import { type ReactNode, useState } from "react";

import { ChevronDown, FolderUp, PlugZap, Plus, Upload } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu-items";

import { useWorkspace } from "../../model/use-workspace";
import { AddKnowledgeDialog } from "./add-knowledge-dialog";
import { ConnectSourceDialog } from "./connect-source-dialog";
import { ShareFilesDialog } from "./share-files-dialog";

type Opening = "share" | "upload" | "connect" | null;

/**
 * The three ways knowledge gets into a workspace, each with who ends up owning it: share your own
 * file (stays yours), upload one (belongs to the workspace), or connect a source (admins).
 */
export function AddKnowledgeMenu({
  picker,
  projectId = null,
  size = "default",
}: {
  /** The account's files to pick from; without it, sharing your own files isn't offered. */
  picker?: ReactNode;
  projectId?: string | null;
  size?: "default" | "sm";
}) {
  const { state, can } = useWorkspace();
  const t = useTranslations("workspaceKnowledge");
  const [opening, setOpening] = useState<Opening>(null);
  const close = (open: boolean) => (open ? undefined : setOpening(null));

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button size={size} variant={size === "sm" ? "outline" : "default"}>
            <Plus data-icon="inline-start" />
            {projectId ? t("addMenu.addFile") : t("addMenu.addKnowledge")}
            <ChevronDown data-icon="inline-end" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-72">
          <DropdownMenuGroup>
            {picker ? (
              <DropdownMenuItem onSelect={() => setOpening("share")} className="items-start">
                <FolderUp className="mt-0.5" />
                <span className="flex flex-col">
                  {t("addMenu.share")}
                  <span className="text-muted-foreground text-xs">{t("addMenu.shareHint")}</span>
                </span>
              </DropdownMenuItem>
            ) : null}
            <DropdownMenuItem onSelect={() => setOpening("upload")} className="items-start">
              <Upload className="mt-0.5" />
              <span className="flex flex-col">
                {t("addMenu.upload", { workspace: state.workspace.name })}
                <span className="text-muted-foreground text-xs">{t("addMenu.uploadHint")}</span>
              </span>
            </DropdownMenuItem>
            {can.admin && !projectId ? (
              <DropdownMenuItem onSelect={() => setOpening("connect")} className="items-start">
                <PlugZap className="mt-0.5" />
                <span className="flex flex-col">
                  {t("addMenu.connect")}
                  <span className="text-muted-foreground text-xs">{t("addMenu.connectHint")}</span>
                </span>
              </DropdownMenuItem>
            ) : null}
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
      {picker ? (
        <ShareFilesDialog open={opening === "share"} onOpenChange={close} picker={picker} projectId={projectId} />
      ) : null}
      <AddKnowledgeDialog open={opening === "upload"} onOpenChange={close} projectId={projectId} />
      {can.admin ? <ConnectSourceDialog open={opening === "connect"} onOpenChange={close} /> : null}
    </>
  );
}
