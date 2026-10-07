"use client";

import { useActionState, useState } from "react";

import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";

import { TASK_TITLE_MAX } from "../../domain/content-contract";
import { createTask } from "../../model/task-actions";
import { useWorkspace } from "../../model/use-workspace";

const NONE = "none";

/** Mounted per opening; a task on a project page starts in that project and with the person who adds it. */
function NewTaskForm({ projectId, onDone }: { projectId: string | null; onDone: () => void }) {
  const { ws, state } = useWorkspace();
  const t = useTranslations("workspaceTasks.form");
  const owner = useTranslations("workspaceTasks.owner");
  const common = useTranslations("common");
  const [title, setTitle] = useState("");
  const [assignee, setAssignee] = useState(state.me_id);
  const [project, setProject] = useState(projectId ?? NONE);
  const [due, setDue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [, submit, pending] = useActionState(async () => {
    if (!title.trim()) setError(t("titleRequired"));
    else {
      const failure = await createTask(ws, {
        title: title.trim(),
        assignee_id: assignee === NONE ? null : assignee,
        due_on: due || null,
        project_id: project === NONE ? null : project,
      });
      if (failure) setError(failure);
      else onDone();
    }
    return null;
  }, null);

  return (
    <form action={submit} noValidate className="flex flex-col gap-4">
      <DialogHeader>
        <DialogTitle>{t("title")}</DialogTitle>
        <DialogDescription>{t("description")}</DialogDescription>
      </DialogHeader>
      <FieldGroup>
        <Field data-invalid={error ? true : undefined}>
          <FieldLabel htmlFor="task-title">{t("task")}</FieldLabel>
          <Input
            id="task-title"
            value={title}
            onChange={(event) => {
              setTitle(event.target.value);
              setError(null);
            }}
            maxLength={TASK_TITLE_MAX}
            placeholder={t("taskPlaceholder")}
            dir="auto"
            autoComplete="off"
            autoFocus
            aria-invalid={error ? true : undefined}
          />
          {error ? <FieldError role="alert">{error}</FieldError> : null}
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field>
            <FieldLabel htmlFor="task-owner">{owner("label")}</FieldLabel>
            <Select value={assignee} onValueChange={setAssignee}>
              <SelectTrigger id="task-owner" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {state.members.map((m) => (
                    <SelectItem key={m.id} value={m.id}>
                      <span dir="auto">{m.id === state.me_id ? owner("meOption", { name: m.name }) : m.name}</span>
                    </SelectItem>
                  ))}
                  <SelectItem value={NONE}>{t("nobodyYet")}</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>
          <Field>
            <FieldLabel htmlFor="task-due">{t("due")}</FieldLabel>
            <Input id="task-due" type="date" value={due} onChange={(event) => setDue(event.target.value)} />
          </Field>
        </div>
        <Field>
          <FieldLabel htmlFor="task-project">{t("project")}</FieldLabel>
          <Select value={project} onValueChange={setProject}>
            <SelectTrigger id="task-project" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem value={NONE}>{t("noProject")}</SelectItem>
                {state.projects.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    <span dir="auto">{p.name}</span>
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
          <FieldDescription>{t("projectHint")}</FieldDescription>
        </Field>
      </FieldGroup>
      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onDone}>
          {common("actions.cancel")}
        </Button>
        <Button type="submit" disabled={pending}>
          {pending ? <Spinner data-icon="inline-start" /> : null}
          {t("submit")}
        </Button>
      </DialogFooter>
    </form>
  );
}

export function NewTaskDialog({
  open,
  onOpenChange,
  projectId = null,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId?: string | null;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        {open ? <NewTaskForm projectId={projectId} onDone={() => onOpenChange(false)} /> : null}
      </DialogContent>
    </Dialog>
  );
}
