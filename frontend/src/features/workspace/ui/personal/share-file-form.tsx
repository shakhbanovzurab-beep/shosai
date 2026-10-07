"use client";

import { useState } from "react";

import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { usePollingResource } from "@/hooks/use-polling-resource";

import type { WorkspaceSummary } from "../../domain/contract";
import type { FileShare } from "../../domain/personal-contract";
import { permissionsOf } from "../../domain/roles";
import { accessAudiences, accessKey, parseAccessKey } from "../../domain/visibility";
import { shareFile, unshareFile } from "../../model/knowledge-actions";
import { resourcesOf, useMyShares, useWorkspaces } from "../../model/resources";
import { ProjectSelect } from "../meetings/project-select";

/** One of the account's files, as the workspace needs to describe it. */
export type ShareableFile = { id: string; name: string; size_bytes: number; content_type: string };

function AccessFields({
  file,
  workspace,
  share,
  onDone,
}: {
  file: ShareableFile;
  workspace: WorkspaceSummary;
  share: FileShare | undefined;
  onDone?: () => void;
}) {
  const state = usePollingResource(resourcesOf(workspace.id).state);
  const knowledge = usePollingResource(resourcesOf(workspace.id).knowledge);
  const [access, setAccess] = useState(share ? accessKey(share.access) : "workspace");
  const current = knowledge.status === "ready" ? knowledge.data.items.find((k) => k.id === share?.item_id) : undefined;
  const [project, setProject] = useState<string | null>(current?.project_id ?? null);
  const t = useTranslations("workspacePersonal");
  const common = useTranslations("common");
  if (state.status !== "ready") return state.status === "error" ? null : <Skeleton className="h-16" />;
  const can = permissionsOf(state.data);
  const { teams } = state.data;
  // The domain picks who may be offered; the words are ours: everyone at the workspace, or a team by name.
  const options = accessAudiences(teams, can.me, can.admin).map((audience) => ({
    key: accessKey(audience),
    label:
      audience.level === "workspace"
        ? t("fileShare.everyone", { workspace: workspace.name })
        : (teams.find((team) => team.id === audience.team_id)?.name ?? ""),
  }));
  const submit = async () => {
    const chosen = parseAccessKey(access);
    const team = teams.find((x) => x.id === chosen.team_id)?.name ?? "";
    const phrase = t("fileShare.toast", { level: chosen.level, file: file.name, team, workspace: workspace.name });
    const { id, name, size_bytes, content_type } = file;
    const request = { file_id: id, name, size_bytes, content_type, access: chosen, project_id: project };
    if (await shareFile(workspace.id, request, phrase)) onDone?.();
  };
  const stop = async () => {
    if (share && (await unshareFile(workspace.id, share.item_id, file.name))) onDone?.();
  };

  return (
    <div className="flex flex-col gap-3">
      <Field>
        <FieldLabel htmlFor={`access-${file.id}-${workspace.id}`}>{t("fileShare.access")}</FieldLabel>
        <Select value={access} onValueChange={setAccess}>
          <SelectTrigger id={`access-${file.id}-${workspace.id}`} className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {options.map((option) => (
                <SelectItem key={option.key} value={option.key}>
                  <span dir="auto">{option.label}</span>
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      </Field>
      <ProjectSelect
        id={`project-${file.id}-${workspace.id}`}
        projects={state.data.projects}
        value={project}
        onChange={setProject}
      />
      <div className="flex justify-end gap-2">
        {share ? (
          <Button variant="ghost" onClick={() => void stop()}>
            {t("stopSharing")}
          </Button>
        ) : null}
        <Button onClick={() => void submit()}>{share ? common("actions.save") : t("share")}</Button>
      </div>
    </div>
  );
}

/**
 * Shares one of the account's files in a workspace's knowledge, so Leo answers from it there for
 * whoever it's for. The workspace points to the file: it stays the account's and leaves with it.
 */
export function ShareFileForm({ file, onDone }: { file: ShareableFile; onDone?: () => void }) {
  const workspaces = useWorkspaces();
  const shares = useMyShares();
  const list = workspaces.status === "ready" ? workspaces.data.workspaces : [];
  const shared = shares.status === "ready" ? shares.data.files.filter((s) => s.file_id === file.id) : [];
  const [workspaceId, setWorkspaceId] = useState(shared[0]?.workspace.id ?? list[0]?.id ?? "");
  const t = useTranslations("workspacePersonal");
  const workspace = list.find((w) => w.id === workspaceId) ?? list[0];
  if (workspaces.status === "loading") return <Skeleton className="h-24" />;
  if (!workspace) return <p className="text-muted-foreground text-sm">{t("fileShare.noWorkspace")}</p>;
  return (
    <FieldGroup className="gap-4">
      {list.length > 1 ? (
        <Field>
          <FieldLabel htmlFor={`share-ws-${file.id}`}>{t("workspace")}</FieldLabel>
          <Select value={workspace.id} onValueChange={setWorkspaceId}>
            <SelectTrigger id={`share-ws-${file.id}`} className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                {list.map((w) => (
                  <SelectItem key={w.id} value={w.id}>
                    <span dir="auto">
                      {shared.some((s) => s.workspace.id === w.id)
                        ? t("fileShare.sharedOption", { workspace: w.name })
                        : w.name}
                    </span>
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        </Field>
      ) : null}
      <AccessFields
        key={workspace.id}
        file={file}
        workspace={workspace}
        share={shared.find((s) => s.workspace.id === workspace.id)}
        onDone={onDone}
      />
    </FieldGroup>
  );
}
