"use client";

import { type ReactNode, useState } from "react";

import Link from "next/link";

import { ArrowUpRight, ChevronDown, Share2 } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import type { WorkspaceSummary } from "../../domain/contract";
import { meetingPath } from "../../domain/paths";
import type { RecordingShare } from "../../domain/personal-contract";
import { useMyShares, useWorkspaces } from "../../model/resources";
import { RecordingShareForm } from "./recording-share-form";

interface WorkspaceSharePanelProps {
  recordingId: string;
  title: string;
  workspaces: WorkspaceSummary[];
  share: RecordingShare | null;
  onDone: () => void;
}

function WorkspaceSharePanel({ recordingId, title, workspaces, share, onDone }: WorkspaceSharePanelProps) {
  const t = useTranslations("workspacePersonal");
  return (
    <div className="flex flex-col gap-2.5">
      <PopoverHeader>
        <PopoverTitle>
          {share ? t("sharedIn", { workspace: share.workspace.name }) : t("recordingShare.title")}
        </PopoverTitle>
        <PopoverDescription>{t("recordingShare.description")}</PopoverDescription>
      </PopoverHeader>
      {share ? (
        <Button asChild variant="link" size="sm" className="h-auto justify-start px-0">
          <Link href={meetingPath(share.workspace.slug, recordingId)}>
            {t("recordingShare.openIn", { workspace: share.workspace.name })}
            <ArrowUpRight data-icon="inline-end" className="rtl:-scale-x-100" />
          </Link>
        </Button>
      ) : null}
      <RecordingShareForm
        recordingId={recordingId}
        title={title}
        workspaces={workspaces}
        share={share}
        onDone={onDone}
      />
    </div>
  );
}

/** Both ways to share as tabs, or whichever one there is. */
function ShareWays({ workspace, link }: { workspace: ReactNode; link: ReactNode }) {
  const t = useTranslations("workspacePersonal.recordingShare");
  if (!workspace || !link) return workspace ?? link;
  return (
    <Tabs defaultValue="workspace" className="gap-4">
      <TabsList className="w-full">
        <TabsTrigger value="workspace">{t("tabWorkspace")}</TabsTrigger>
        <TabsTrigger value="link">{t("tabLink")}</TabsTrigger>
      </TabsList>
      <TabsContent value="workspace">{workspace}</TabsContent>
      <TabsContent value="link">{link}</TabsContent>
    </Tabs>
  );
}

interface RecordingShareButtonProps {
  recordingId: string;
  title: string;
  /** Another way to share, shown as a tab next to the workspace, e.g. a link for people outside the meeting. */
  linkShare?: ReactNode;
}

/**
 * On a recording in your Notes: share it to one of your workspaces, change who sees it there, move it,
 * or stop sharing, and any other way to share passed in. Without a workspace only those other ways show;
 * with neither, nothing does.
 */
export function RecordingShareButton({ recordingId, title, linkShare }: RecordingShareButtonProps) {
  const [open, setOpen] = useState(false);
  const workspaces = useWorkspaces();
  const shares = useMyShares();
  const t = useTranslations("workspacePersonal");
  const ready = workspaces.status === "ready" && shares.status === "ready";
  const available = ready && workspaces.data.workspaces.length > 0 ? workspaces.data.workspaces : null;
  if (!available && !linkShare) return null;
  const share = ready ? (shares.data.recordings.find((r) => r.recording_id === recordingId) ?? null) : null;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant={share ? "outline" : "default"} size="sm">
          <Share2 data-icon="inline-start" />
          {share ? t("sharedIn", { workspace: share.workspace.name }) : t("share")}
          <ChevronDown data-icon="inline-end" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-96">
        <ShareWays
          workspace={
            available ? (
              <WorkspaceSharePanel
                recordingId={recordingId}
                title={title}
                workspaces={available}
                share={share}
                onDone={() => setOpen(false)}
              />
            ) : null
          }
          link={linkShare ?? null}
        />
      </PopoverContent>
    </Popover>
  );
}
