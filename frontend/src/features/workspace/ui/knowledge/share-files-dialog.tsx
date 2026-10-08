"use client";

import { type ReactNode, useActionState, useState } from "react";

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
import { FieldGroup } from "@/components/ui/field";
import { FieldError } from "@/components/ui/field-text";
import { Spinner } from "@/components/ui/spinner";

import { parseAccessKey } from "../../domain/visibility";
import { shareFiles } from "../../model/knowledge-actions";
import { useMyShares } from "../../model/resources";
import { useWorkspace } from "../../model/use-workspace";
import type { ShareableFile } from "../personal/share-file-form";
import { AccessField, KnowledgeProjectField } from "./access-field";
import { type FileSelection, FileSelectionContext } from "./file-selection";

/** Mounted per opening, so each time starts with nothing picked. */
function ShareFilesForm({
  picker,
  initialProject,
  onDone,
}: {
  picker: ReactNode;
  initialProject: string | null;
  onDone: () => void;
}) {
  const { ws, state } = useWorkspace();
  const t = useTranslations("workspaceKnowledgeDialogs");
  const common = useTranslations("common");
  const shares = useMyShares();
  const [picked, setPicked] = useState<ReadonlyMap<string, ShareableFile>>(new Map());
  const [access, setAccess] = useState("workspace");
  const [project, setProject] = useState(initialProject);
  const [error, setError] = useState<string | null>(null);
  const sharedHere = new Set(
    shares.status === "ready" ? shares.data.files.filter((s) => s.workspace.id === ws).map((s) => s.file_id) : [],
  );
  const selection: FileSelection = {
    isSelected: (id) => picked.has(id),
    toggle: (file) => {
      const next = new Map(picked);
      if (next.has(file.id)) next.delete(file.id);
      else next.set(file.id, file);
      setPicked(next);
    },
    sharedHere,
  };

  const [, submit, pending] = useActionState(async () => {
    const chosen = parseAccessKey(access);
    const requests = [...picked.values()].map((f) => ({
      file_id: f.id,
      name: f.name,
      size_bytes: f.size_bytes,
      content_type: f.content_type,
      access: chosen,
      project_id: project,
    }));
    const failure = await shareFiles(ws, requests);
    if (failure) setError(failure);
    else onDone();
    return null;
  }, null);

  return (
    <form action={submit} noValidate className="flex min-h-0 flex-col gap-4">
      <DialogHeader>
        <DialogTitle>{t("share.title")}</DialogTitle>
        <DialogDescription>{t("share.description", { workspace: state.workspace.name })}</DialogDescription>
      </DialogHeader>
      <FileSelectionContext value={selection}>{picker}</FileSelectionContext>
      <FieldGroup className="gap-4">
        <AccessField id="share-files-access" value={access} onChange={setAccess} />
        <KnowledgeProjectField id="share-files-project" value={project} onChange={setProject} />
        {error ? <FieldError role="alert">{error}</FieldError> : null}
      </FieldGroup>
      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onDone}>
          {common("actions.cancel")}
        </Button>
        <Button type="submit" disabled={pending || picked.size === 0}>
          {pending ? <Spinner data-icon="inline-start" /> : null}
          {t("share.submit", { count: picked.size })}
        </Button>
      </DialogFooter>
    </form>
  );
}

/** Pick files from the account's File Manager (the `picker`) and share them in the current workspace. */
export function ShareFilesDialog({
  open,
  onOpenChange,
  picker,
  projectId = null,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  picker: ReactNode;
  projectId?: string | null;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[90dvh] flex-col sm:max-w-lg">
        {open ? <ShareFilesForm picker={picker} initialProject={projectId} onDone={() => onOpenChange(false)} /> : null}
      </DialogContent>
    </Dialog>
  );
}
