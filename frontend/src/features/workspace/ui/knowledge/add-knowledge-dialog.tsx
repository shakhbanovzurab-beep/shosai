"use client";

import { useActionState, useRef, useState } from "react";

import { cn } from "cn";
import { CloudUpload, X } from "lucide-react";
import { useFormatter, useLocale, useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { FieldError, FieldGroup } from "@/components/ui/field";
import { Spinner } from "@/components/ui/spinner";
import { formatBytes } from "@/i18n/format-units";

import { KNOWLEDGE_FILE_MAX_BYTES, KNOWLEDGE_FILES_PER_UPLOAD } from "../../domain/knowledge-contract";
import { parseAccessKey } from "../../domain/visibility";
import { addKnowledge } from "../../model/knowledge-actions";
import { useWorkspace } from "../../model/use-workspace";
import { AccessField, KnowledgeProjectField } from "./access-field";

const ACCEPT = ".pdf,.doc,.docx,.md,.txt,.xls,.xlsx,.csv,.ppt,.pptx";

/** Mounted per opening, so each upload starts empty. */
function AddKnowledgeForm({ initialProject, onDone }: { initialProject: string | null; onDone: () => void }) {
  const { ws, state } = useWorkspace();
  const t = useTranslations("workspaceKnowledgeDialogs");
  const common = useTranslations("common");
  const format = useFormatter();
  const locale = useLocale();
  const limit = formatBytes(locale, KNOWLEDGE_FILE_MAX_BYTES);
  const workspace = state.workspace.name;
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [access, setAccess] = useState("workspace");
  const [project, setProject] = useState(initialProject);
  const [over, setOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pick = (picked: File[]) => {
    const tooBig = picked.filter((f) => f.size > KNOWLEDGE_FILE_MAX_BYTES);
    const next = [...files, ...picked.filter((f) => f.size <= KNOWLEDGE_FILE_MAX_BYTES)].slice(
      0,
      KNOWLEDGE_FILES_PER_UPLOAD,
    );
    setFiles(next);
    const names = format.list(tooBig.map((f) => f.name));
    setError(tooBig.length > 0 ? t("upload.tooBig", { count: tooBig.length, names, limit }) : null);
  };

  const [, submit, pending] = useActionState(async () => {
    if (files.length === 0) setError(t("upload.noFiles"));
    else {
      const failure = await addKnowledge(ws, files, parseAccessKey(access), project);
      if (failure) setError(failure);
      else onDone();
    }
    return null;
  }, null);

  return (
    <form action={submit} noValidate className="flex flex-col gap-4">
      <DialogHeader>
        <DialogTitle>{t("upload.title", { workspace })}</DialogTitle>
        <DialogDescription>{t("upload.description", { workspace })}</DialogDescription>
      </DialogHeader>
      <FieldGroup>
        <section
          aria-label={t("upload.dropZone")}
          onDragOver={(event) => {
            event.preventDefault();
            setOver(true);
          }}
          onDragLeave={() => setOver(false)}
          onDrop={(event) => {
            event.preventDefault();
            setOver(false);
            pick([...event.dataTransfer.files]);
          }}
          className={cn(
            "flex flex-col items-center gap-2 rounded-xl border border-dashed bg-muted/30 px-4 py-6 text-center transition-colors",
            over && "border-primary bg-primary/5",
          )}
        >
          <CloudUpload className="size-5 text-muted-foreground" aria-hidden="true" />
          <p className="text-sm">{t("upload.drop")}</p>
          <Button type="button" variant="outline" size="sm" onClick={() => inputRef.current?.click()}>
            {t("upload.choose")}
          </Button>
          <p className="text-muted-foreground text-xs">{t("upload.formats", { limit })}</p>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept={ACCEPT}
            className="sr-only"
            tabIndex={-1}
            aria-hidden="true"
            onChange={(event) => {
              pick([...(event.currentTarget.files ?? [])]);
              event.currentTarget.value = "";
            }}
          />
        </section>
        {files.length > 0 ? (
          <ul
            className="flex max-h-40 flex-col divide-y overflow-y-auto rounded-lg border"
            aria-label={t("upload.chosen")}
          >
            {files.map((file, index) => (
              <li
                key={`${file.name}-${file.size}-${file.lastModified}`}
                className="flex items-center gap-2 px-3 py-1.5 text-sm"
              >
                <span dir="auto" className="min-w-0 flex-1 truncate">
                  {file.name}
                </span>
                <span className="shrink-0 text-muted-foreground text-xs tabular-nums">
                  {formatBytes(locale, file.size)}
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-xs"
                  aria-label={t("upload.removeFile", { name: file.name })}
                  onClick={() => setFiles(files.filter((_, i) => i !== index))}
                >
                  <X />
                </Button>
              </li>
            ))}
          </ul>
        ) : null}
        <AccessField id="knowledge-access" value={access} onChange={setAccess} />
        <KnowledgeProjectField id="knowledge-project" value={project} onChange={setProject} />
        {error ? <FieldError role="alert">{error}</FieldError> : null}
      </FieldGroup>
      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onDone}>
          {common("actions.cancel")}
        </Button>
        <Button type="submit" disabled={pending || files.length === 0}>
          {pending ? <Spinner data-icon="inline-start" /> : null}
          {t("upload.submit", { count: files.length })}
        </Button>
      </DialogFooter>
    </form>
  );
}

/** Uploads files that belong to the workspace, optionally straight into a project. */
export function AddKnowledgeDialog({
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
        {open ? <AddKnowledgeForm initialProject={projectId} onDone={() => onOpenChange(false)} /> : null}
      </DialogContent>
    </Dialog>
  );
}
