"use client";

import { useActionState, useState } from "react";

import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldGroup } from "@/components/ui/field";
import { FieldError, FieldLabel } from "@/components/ui/field-text";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { useRouter } from "@/lib/navigation";

import { PROJECT_NAME_MAX, PROJECT_STATUSES, type Project, type ProjectStatus } from "../../domain/contract";
import { saveProject } from "../../model/group-actions";
import { useWorkspace } from "../../model/use-workspace";

const NONE = "none";
const isStatus = (value: string): value is ProjectStatus => PROJECT_STATUSES.some((s) => s === value);

/** Mounted per opening: a new project starts active and led by whoever creates it. */
function ProjectForm({ project, onDone }: { project: Project | null; onDone: () => void }) {
  const { ws, state, path } = useWorkspace();
  const router = useRouter();
  const t = useTranslations("workspaceProjects");
  const common = useTranslations("common");
  const [name, setName] = useState(project?.name ?? "");
  const [description, setDescription] = useState(project?.description ?? "");
  const [status, setStatus] = useState<ProjectStatus>(project?.status ?? "active");
  const [lead, setLead] = useState(project?.lead_id ?? state.me_id);
  const [team, setTeam] = useState(project?.team_id ?? NONE);
  const [target, setTarget] = useState(project?.target_date ?? "");
  const [error, setError] = useState<string | null>(null);

  const [, submit, pending] = useActionState(async () => {
    if (!name.trim()) {
      setError(t("dialog.nameRequired"));
      return null;
    }
    const input = {
      name: name.trim(),
      description: description.trim(),
      status,
      lead_id: lead === NONE ? null : lead,
      team_id: team === NONE ? null : team,
      target_date: target || null,
    };
    const done = project ? t("dialog.saved", { name: input.name }) : t("dialog.created", { name: input.name });
    const result = await saveProject(ws, project?.id ?? null, input, done);
    if ("error" in result) setError(result.error);
    else {
      onDone();
      if (!project && result.id) router.push(path(`/projects/${result.id}`));
    }
    return null;
  }, null);

  return (
    <form action={submit} noValidate className="flex flex-col gap-4">
      <DialogHeader>
        <DialogTitle>{project ? t("dialog.editTitle", { name: project.name }) : t("dialog.newTitle")}</DialogTitle>
        <DialogDescription>{t("dialog.description")}</DialogDescription>
      </DialogHeader>
      <FieldGroup>
        <Field data-invalid={error ? true : undefined}>
          <FieldLabel htmlFor="project-name">{common("fields.name")}</FieldLabel>
          <Input
            id="project-name"
            value={name}
            onChange={(event) => {
              setName(event.target.value);
              setError(null);
            }}
            maxLength={PROJECT_NAME_MAX}
            dir="auto"
            placeholder={t("dialog.namePlaceholder")}
            autoComplete="off"
            autoFocus
            aria-invalid={error ? true : undefined}
          />
          {error ? <FieldError role="alert">{error}</FieldError> : null}
        </Field>
        <Field>
          <FieldLabel htmlFor="project-description">{t("dialog.purpose")}</FieldLabel>
          <Textarea
            id="project-description"
            dir="auto"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
          />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field>
            <FieldLabel htmlFor="project-lead">{t("dialog.lead")}</FieldLabel>
            <Select value={lead} onValueChange={setLead}>
              <SelectTrigger id="project-lead" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {state.members.map((m) => (
                    <SelectItem key={m.id} value={m.id}>
                      <span dir="auto">{m.id === state.me_id ? t("dialog.me", { name: m.name }) : m.name}</span>
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>
          <Field>
            <FieldLabel htmlFor="project-team">{t("dialog.team")}</FieldLabel>
            <Select value={team} onValueChange={setTeam}>
              <SelectTrigger id="project-team" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value={NONE}>{t("dialog.wholeWorkspace")}</SelectItem>
                  {state.teams.map((x) => (
                    <SelectItem key={x.id} value={x.id}>
                      <span dir="auto">{x.name}</span>
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>
          <Field>
            <FieldLabel htmlFor="project-status">{t("dialog.status")}</FieldLabel>
            <Select value={status} onValueChange={(value) => (isStatus(value) ? setStatus(value) : undefined)}>
              <SelectTrigger id="project-status" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {PROJECT_STATUSES.map((s) => (
                    <SelectItem key={s} value={s}>
                      {t(`status.${s}`)}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>
          <Field>
            <FieldLabel htmlFor="project-target">{t("dialog.target")}</FieldLabel>
            <Input id="project-target" type="date" value={target} onChange={(e) => setTarget(e.target.value)} />
          </Field>
        </div>
      </FieldGroup>
      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onDone}>
          {common("actions.cancel")}
        </Button>
        <Button type="submit" disabled={pending}>
          {pending ? <Spinner data-icon="inline-start" /> : null}
          {project ? common("actions.save") : t("dialog.create")}
        </Button>
      </DialogFooter>
    </form>
  );
}

export function ProjectDialog({
  project,
  open,
  onOpenChange,
}: {
  project: Project | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        {open ? <ProjectForm project={project} onDone={() => onOpenChange(false)} /> : null}
      </DialogContent>
    </Dialog>
  );
}
