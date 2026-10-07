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
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { meetingNotes } from "@/features/notes";

import { parseVisibilityKey, visibilityKey } from "../../domain/visibility";
import { shareRecording } from "../../model/meeting-actions";
import { useMyShares } from "../../model/resources";
import { useWorkspace } from "../../model/use-workspace";
import { ProjectSelect } from "./project-select";
import { useAudienceWords } from "./use-audience-words";
import { useMeetingWhen } from "./use-meeting-when";

/** Mounted per opening: pick one of your recordings, who sees it, and its project. */
function ShareRecordingForm({ onDone }: { onDone: () => void }) {
  const { ws, state, can } = useWorkspace();
  const shares = useMyShares();
  const t = useTranslations("workspaceMeetings.shareDialog");
  const common = useTranslations("common");
  const when = useMeetingWhen();
  const words = useAudienceWords({ teams: state.teams, workspaceName: state.workspace.name });
  const sharedHere = new Set(
    shares.status === "ready"
      ? shares.data.recordings.filter((r) => r.workspace.id === ws).map((r) => r.recording_id)
      : [],
  );
  const elsewhere = new Map(
    shares.status === "ready"
      ? shares.data.recordings.filter((r) => r.workspace.id !== ws).map((r) => [r.recording_id, r.workspace.name])
      : [],
  );
  const choices = meetingNotes.filter((note) => !sharedHere.has(note.id));
  const options = words.options(can.me, can.admin);
  const [recording, setRecording] = useState(choices[0]?.id ?? "");
  const [audience, setAudience] = useState(
    state.workspace.sharing.default_level === "workspace" ? "workspace" : "participants",
  );
  const [project, setProject] = useState<string | null>(null);
  const movedFrom = elsewhere.get(recording);

  const [, submit, pending] = useActionState(async () => {
    const note = choices.find((n) => n.id === recording);
    if (!note) return null;
    const visibility = parseVisibilityKey(audience);
    const shared = await shareRecording(
      ws,
      {
        recording_id: note.id,
        visibility,
        project_id: project,
        transcript_shared: state.workspace.sharing.share_transcripts,
      },
      words.sharedToast(visibility, note.title),
    );
    if (shared) onDone();
    return null;
  }, null);

  if (choices.length === 0)
    return (
      <>
        <DialogHeader>
          <DialogTitle>{t("allSharedTitle")}</DialogTitle>
          <DialogDescription>{t("allShared", { workspace: state.workspace.name })}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button onClick={onDone}>{common("actions.close")}</Button>
        </DialogFooter>
      </>
    );

  return (
    <form action={submit} className="flex flex-col gap-4">
      <DialogHeader>
        <DialogTitle>{t("title")}</DialogTitle>
        <DialogDescription>{t("description", { workspace: state.workspace.name })}</DialogDescription>
      </DialogHeader>
      <FieldGroup>
        <Field>
          <FieldLabel htmlFor="share-recording">{t("meeting")}</FieldLabel>
          <Select value={recording} onValueChange={setRecording}>
            <SelectTrigger id="share-recording" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                {choices.map((note) => (
                  <SelectItem key={note.id} value={note.id}>
                    <span dir="auto">{note.title}</span> · {when.date(note.startedAt)}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
          {movedFrom ? <FieldDescription>{t("movesFrom", { workspace: movedFrom })}</FieldDescription> : null}
        </Field>
        <Field>
          <FieldLabel htmlFor="share-audience">{t("audience")}</FieldLabel>
          <Select value={audience} onValueChange={setAudience}>
            <SelectTrigger id="share-audience" className="w-full">
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
          <FieldDescription>{t("audienceHint")}</FieldDescription>
        </Field>
        <ProjectSelect id="share-project" projects={state.projects} value={project} onChange={setProject} />
      </FieldGroup>
      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onDone}>
          {common("actions.cancel")}
        </Button>
        <Button type="submit" disabled={pending || !recording}>
          {pending ? <Spinner data-icon="inline-start" /> : null}
          {t("submit")}
        </Button>
      </DialogFooter>
    </form>
  );
}

export function ShareRecordingDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        {open ? <ShareRecordingForm onDone={() => onOpenChange(false)} /> : null}
      </DialogContent>
    </Dialog>
  );
}
