"use client";

import { useState, useTransition } from "react";

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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { useAutosave } from "@/hooks/use-autosave";

import { PROMPT_CONTENT_MAX, PROMPT_NAME_MAX, type PromptDraft, type Skill } from "../domain/contract";
import { createPrompt, savePromptDraft } from "../model/prompt-actions";
import { RoleSelect } from "./role-select";
import { SkillPicker } from "./skill-picker";

/** Writing a new prompt, or editing one of yours (edits save themselves). */
export type EditorTarget = { mode: "create"; draft: PromptDraft } | { mode: "edit"; id: string; draft: PromptDraft };

type EditorFormProps = { editingId: string | null; initialDraft: PromptDraft; skills: Skill[]; onClose: () => void };

function EditorForm({ editingId, initialDraft, skills, onClose }: EditorFormProps) {
  const t = useTranslations("studioPrompts");
  const ts = useTranslations("studio");
  const tc = useTranslations("common");
  const [draft, setDraft] = useState(initialDraft);
  const [creating, startCreating] = useTransition();
  const autosave = useAutosave((value) => savePromptDraft(editingId ?? "", JSON.parse(value) as PromptDraft));

  const set = <K extends keyof PromptDraft>(key: K, value: PromptDraft[K]) => {
    const next = { ...draft, [key]: value };
    setDraft(next);
    if (editingId && next.name.trim()) autosave.schedule(JSON.stringify(next));
  };

  const create = () =>
    startCreating(async () => {
      if (await createPrompt(draft, t)) onClose();
    });

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-[1fr_12rem]">
        <div className="flex flex-col gap-2">
          <Label htmlFor="prompt-name">{tc("fields.name")}</Label>
          <Input
            id="prompt-name"
            dir="auto"
            value={draft.name}
            maxLength={PROMPT_NAME_MAX}
            onChange={(e) => set("name", e.currentTarget.value)}
            placeholder={t("editor.namePlaceholder")}
          />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="prompt-role">{t("role")}</Label>
          <RoleSelect id="prompt-role" value={draft.role} onChange={(role) => set("role", role)} />
        </div>
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="prompt-content">{t("editor.instructions")}</Label>
        <Textarea
          id="prompt-content"
          dir="auto"
          value={draft.content}
          maxLength={PROMPT_CONTENT_MAX}
          onChange={(e) => set("content", e.currentTarget.value)}
          placeholder={t("editor.instructionsPlaceholder")}
          className="min-h-48 font-mono text-sm leading-6"
        />
      </div>
      <div className="flex flex-col gap-2">
        <span className="font-medium text-sm">{t("skills")}</span>
        <SkillPicker skills={skills} value={draft.skill_ids} onChange={(ids) => set("skill_ids", ids)} />
      </div>
      <DialogFooter className="items-center">
        {editingId ? (
          <>
            <span className="me-auto text-muted-foreground text-xs" aria-live="polite">
              {autosave.status === "error" ? t("editor.saveFailed") : null}
              {autosave.status === "saving" || autosave.status === "pending" ? ts("autosave.saving") : null}
              {autosave.status === "idle" ? t("editor.savesAutomatically") : null}
            </span>
            <Button
              onClick={() => {
                autosave.flush();
                onClose();
              }}
            >
              {t("editor.done")}
            </Button>
          </>
        ) : (
          <Button disabled={!draft.name.trim() || creating} onClick={create}>
            {creating ? <Spinner data-icon="inline-start" /> : null}
            {tc("actions.create")}
          </Button>
        )}
      </DialogFooter>
    </div>
  );
}

type PromptEditorDialogProps = { target: EditorTarget | null; skills: Skill[]; onClose: () => void };

export function PromptEditorDialog({ target, skills, onClose }: PromptEditorDialogProps) {
  const t = useTranslations("studioPrompts");
  return (
    <Dialog open={target !== null} onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{target?.mode === "edit" ? t("editor.editTitle") : t("editor.newTitle")}</DialogTitle>
          <DialogDescription>{t("editor.description")}</DialogDescription>
        </DialogHeader>
        {target ? (
          <EditorForm
            key={target.mode === "edit" ? target.id : "new"}
            editingId={target.mode === "edit" ? target.id : null}
            initialDraft={target.draft}
            skills={skills}
            onClose={onClose}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
