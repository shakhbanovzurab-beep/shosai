"use client";

import { useState } from "react";

import { ChevronDown, TriangleAlert, Undo2 } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";

import type { TeamMeetingDetail } from "../../domain/content-contract";
import { isAdmin } from "../../domain/roles";
import { parseVisibilityKey, visibilityKey } from "../../domain/visibility";
import { unshareMeeting, updateMeeting } from "../../model/meeting-actions";
import { useWorkspace } from "../../model/use-workspace";
import { VisibilityBadge } from "../shared/badges";
import { ProjectSelect } from "./project-select";
import { useAudienceWords } from "./use-audience-words";

/**
 * Who sees a shared meeting inside the workspace, narrowest to widest; each change applies at once
 * with Undo. Its organizer can also stop sharing it (it stays in their Notes); an admin can take it
 * out. Everyone else sees the same badge, and why they can't change it.
 */
export function ShareControl({ meeting }: { meeting: TeamMeetingDetail }) {
  const { ws, state, can } = useWorkspace();
  const [open, setOpen] = useState(false);
  const byMe = meeting.organizer_id === state.me_id;
  const context = { teams: state.teams, workspaceName: state.workspace.name };
  const t = useTranslations("workspaceMeetings.share");
  const audience = useAudienceWords(context);

  if (!byMe && !can.admin)
    return (
      <span title={t("lockedHint")}>
        <VisibilityBadge visibility={meeting.visibility} {...context} />
      </span>
    );

  const options = audience.options(can.me, isAdmin(can.me));
  const current = visibilityKey(meeting.visibility);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" title={t("change")}>
          {audience.sharedWith(meeting.visibility)}
          <ChevronDown data-icon="inline-end" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80">
        <PopoverHeader>
          <PopoverTitle>{t("title")}</PopoverTitle>
          <PopoverDescription>{t("description")}</PopoverDescription>
        </PopoverHeader>
        {meeting.external ? (
          <p className="flex gap-2 rounded-md bg-muted px-3 py-2 text-xs">
            <TriangleAlert className="mt-px size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
            {t("external", { workspace: state.workspace.name })}
          </p>
        ) : null}
        <RadioGroup
          value={current}
          aria-label={t("audienceLabel")}
          onValueChange={(key) => {
            if (key === current) return;
            const next = parseVisibilityKey(key);
            void updateMeeting(ws, meeting.id, { visibility: next }, audience.sharedWith(next), {
              visibility: meeting.visibility,
            });
          }}
          className="gap-1"
        >
          {options.map((option) => {
            const key = visibilityKey(option.visibility);
            const id = `share-${meeting.id}-${key}`;
            return (
              <Label
                key={key}
                htmlFor={id}
                className="flex cursor-pointer items-start gap-3 rounded-md px-2 py-2 font-normal hover:bg-muted has-data-[state=checked]:bg-muted"
              >
                <RadioGroupItem id={id} value={key} className="mt-0.5" />
                <span className="flex min-w-0 flex-col gap-0.5">
                  <span className="font-medium text-sm" dir="auto">
                    {option.label}
                  </span>
                  <span className="text-muted-foreground text-xs">{option.description}</span>
                </span>
              </Label>
            );
          })}
        </RadioGroup>
        <Separator />
        <div className="flex items-center justify-between gap-4">
          <Label htmlFor={`transcript-${meeting.id}`} className="flex flex-col items-start gap-0.5 font-normal">
            <span className="font-medium text-sm">{t("includeTranscript")}</span>
            <span className="text-muted-foreground text-xs">{t("includeTranscriptHint")}</span>
          </Label>
          <Switch
            id={`transcript-${meeting.id}`}
            checked={meeting.transcript_shared}
            onCheckedChange={(checked) =>
              void updateMeeting(
                ws,
                meeting.id,
                { transcript_shared: checked },
                checked ? t("transcriptShared") : t("summaryOnly"),
              )
            }
          />
        </div>
        <ProjectSelect
          id={`project-${meeting.id}`}
          projects={state.projects}
          value={meeting.project_id}
          onChange={(project_id) =>
            void updateMeeting(
              ws,
              meeting.id,
              { project_id },
              project_id ? t("addedToProject") : t("removedFromProject"),
            )
          }
        />
        <Separator />
        <Button
          variant="ghost"
          size="sm"
          className="justify-start text-muted-foreground"
          onClick={() => {
            setOpen(false);
            void unshareMeeting(
              ws,
              meeting.id,
              byMe
                ? {
                    recording_id: meeting.id,
                    visibility: meeting.visibility,
                    project_id: meeting.project_id,
                    transcript_shared: meeting.transcript_shared,
                  }
                : null,
              byMe,
            );
          }}
        >
          <Undo2 data-icon="inline-start" className="rtl:-scale-x-100" />
          {byMe ? t("stopMine") : t("takeOut", { workspace: state.workspace.name })}
        </Button>
      </PopoverContent>
    </Popover>
  );
}
