"use client";

import { useActionState, useState } from "react";

import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Field, FieldGroup } from "@/components/ui/field";
import { FieldDescription, FieldLabel } from "@/components/ui/field-text";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { usePollingResource } from "@/hooks/use-polling-resource";

import type { WorkspaceSummary } from "../../domain/contract";
import type { RecordingShare } from "../../domain/personal-contract";
import { permissionsOf } from "../../domain/roles";
import { parseVisibilityKey, visibilityKey } from "../../domain/visibility";
import { shareRecording, unshareMeeting } from "../../model/meeting-actions";
import { resourcesOf } from "../../model/resources";
import { ProjectSelect } from "../meetings/project-select";
import { useAudienceWords } from "../meetings/use-audience-words";

type FormProps = {
  recordingId: string;
  title: string;
  workspace: WorkspaceSummary;
  share: RecordingShare | null;
  onDone: () => void;
};

/** Audience, project and transcript for one workspace, from that workspace's own teams and projects. */
function AudienceFields({ recordingId, title, workspace, share, onDone }: FormProps) {
  const state = usePollingResource(resourcesOf(workspace.id).state);
  const here = share?.workspace.id === workspace.id ? share : null;
  const [audience, setAudience] = useState(here ? visibilityKey(here.visibility) : "participants");
  const [project, setProject] = useState<string | null>(here?.project_id ?? null);
  const [transcript, setTranscript] = useState(here?.transcript_shared ?? false);
  const t = useTranslations("workspacePersonal");
  const meetings = useTranslations("workspaceMeetings");
  const common = useTranslations("common");
  const words = useAudienceWords({
    teams: state.status === "ready" ? state.data.teams : [],
    workspaceName: workspace.name,
  });

  const [, submit, pending] = useActionState(async () => {
    if (state.status !== "ready") return null;
    const visibility = parseVisibilityKey(audience);
    const phrase = words.sharedToast(visibility, title);
    const request = { recording_id: recordingId, visibility, project_id: project, transcript_shared: transcript };
    if (await shareRecording(workspace.id, request, phrase, share?.workspace.id)) onDone();
    return null;
  }, null);

  if (state.status !== "ready")
    return state.status === "error" ? (
      <p className="text-destructive text-sm">{t("recordingShare.loadFailed", { workspace: workspace.name })}</p>
    ) : (
      <Skeleton className="h-28" />
    );
  const can = permissionsOf(state.data);
  let submitLabel = t("share");
  if (here) submitLabel = common("actions.save");
  else if (share) submitLabel = t("recordingShare.moveTo", { workspace: workspace.name });
  const options = words.options(can.me, can.admin);

  return (
    <form action={submit} className="flex flex-col gap-4">
      <FieldGroup className="gap-4">
        <Field>
          <FieldLabel htmlFor={`audience-${recordingId}`}>{meetings("shareDialog.audience")}</FieldLabel>
          <Select value={audience} onValueChange={setAudience}>
            <SelectTrigger id={`audience-${recordingId}`} className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                {options.map((option) => (
                  <SelectItem key={visibilityKey(option.visibility)} value={visibilityKey(option.visibility)}>
                    <span dir="auto">{option.label}</span>
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
          <FieldDescription>{t("recordingShare.audienceHint")}</FieldDescription>
        </Field>
        <ProjectSelect
          id={`project-${recordingId}`}
          projects={state.data.projects}
          value={project}
          onChange={setProject}
        />
        <div className="flex items-center justify-between gap-4">
          <Label htmlFor={`transcript-${recordingId}`} className="font-medium text-sm">
            {meetings("share.includeTranscript")}
          </Label>
          <Switch id={`transcript-${recordingId}`} checked={transcript} onCheckedChange={setTranscript} />
        </div>
      </FieldGroup>
      <div className="flex flex-wrap justify-end gap-2">
        {here ? (
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              onDone();
              void unshareMeeting(workspace.id, recordingId, {
                recording_id: recordingId,
                visibility: here.visibility,
                project_id: here.project_id,
                transcript_shared: here.transcript_shared,
              });
            }}
          >
            {t("stopSharing")}
          </Button>
        ) : null}
        <Button type="submit" disabled={pending}>
          {pending ? <Spinner data-icon="inline-start" /> : null}
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}

/**
 * Sharing one of your recordings: pick a workspace (one at a time), then who sees it there. The
 * recording stays in your Notes either way; stopping sharing takes it back out of the workspace.
 */
export function RecordingShareForm({
  recordingId,
  title,
  workspaces,
  share,
  onDone,
}: Omit<FormProps, "workspace"> & { workspaces: WorkspaceSummary[] }) {
  const [workspaceId, setWorkspaceId] = useState(share?.workspace.id ?? workspaces[0]?.id ?? "");
  const workspace = workspaces.find((w) => w.id === workspaceId);
  const t = useTranslations("workspacePersonal");
  return (
    <div className="flex flex-col gap-4">
      {workspaces.length > 1 ? (
        <Field>
          <FieldLabel htmlFor={`workspace-${recordingId}`}>{t("workspace")}</FieldLabel>
          <Select value={workspaceId} onValueChange={setWorkspaceId}>
            <SelectTrigger id={`workspace-${recordingId}`} className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                {workspaces.map((w) => (
                  <SelectItem key={w.id} value={w.id}>
                    <span dir="auto">{w.name}</span>
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
          {share && share.workspace.id !== workspaceId ? (
            <FieldDescription>
              {t("recordingShare.sharedElsewhere", { workspace: share.workspace.name })}
            </FieldDescription>
          ) : null}
        </Field>
      ) : null}
      {workspace ? (
        <AudienceFields
          key={workspace.id}
          recordingId={recordingId}
          title={title}
          workspace={workspace}
          share={share}
          onDone={onDone}
        />
      ) : null}
    </div>
  );
}
