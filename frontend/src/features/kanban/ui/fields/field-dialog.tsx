"use client";

import { useId, useState } from "react";

import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, FieldGroup } from "@/components/ui/field";
import { FieldError, FieldLabel } from "@/components/ui/field-text";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";

import { clearedBy, fieldDraftProblem } from "../../domain/field-rules";
import { type CustomKind, type CustomSticker, STATES_MAX, STICKER_NAME_MAX } from "../../domain/stickers-contract";
import { useOwnedStickers } from "../../model/stickers-resource";
import { useBoardCommands } from "../board-store";
import { DeleteFieldButton, KindPicker } from "./field-dialog-parts";
import { draftsOf, newStateDraft, removedStates, type StateDraft, statesOf } from "./state-drafts";
import { StatesEditor } from "./states-editor";

/** Что открыть: новое поле или правку своего. */
export type FieldRequest = { mode: "new" } | { mode: "edit"; sticker: CustomSticker };

type Draft = { kind: CustomKind; name: string; states: StateDraft[] };

const draftOf = (sticker: CustomSticker | null): Draft =>
  sticker
    ? { kind: sticker.kind, name: sticker.name, states: draftsOf(sticker) }
    : { kind: "states", name: "", states: [newStateDraft(0)] };

/** Своё поле со счётом его значений — для предупреждений правки и удаления. */
function useOwned(sticker: CustomSticker | null) {
  const owned = useOwnedStickers();
  return owned.status === "ready" && sticker ? owned.data.items.find((item) => item.id === sticker.id) : undefined;
}

/** Форма поля: вид (у нового), имя, набор состояний; правка ещё и удаляет поле. */
function FieldForm({ sticker, onDone }: { sticker: CustomSticker | null; onDone: () => void }) {
  const t = useTranslations("kanbanFields");
  const tc = useTranslations("common");
  const { fields } = useBoardCommands();
  const owned = useOwned(sticker);
  const [draft, setDraft] = useState(() => draftOf(sticker));
  const [tried, setTried] = useState(false);
  const [saving, setSaving] = useState(false);
  const nameId = useId();
  const problem = fieldDraftProblem(draft.kind, draft.name, draft.states);
  const clears = owned ? clearedBy(owned.usage, removedStates(sticker, draft.states)) : 0;
  const nameInvalid = tried && problem?.startsWith("name") ? true : undefined;

  const save = async () => {
    const name = draft.name.trim();
    const states = draft.kind === "states" ? { states: statesOf(draft.states) } : {};
    if (sticker) return fields.edit(sticker, { name, ...states });
    return (await fields.place({ kind: draft.kind, name, ...states })) !== null;
  };
  const submit = () => {
    setTried(true);
    if (problem) return;
    setSaving(true);
    void save()
      .then((done) => (done ? onDone() : undefined))
      .finally(() => setSaving(false));
  };

  return (
    <form
      className="flex flex-col gap-5"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <DialogHeader>
        <DialogTitle>{t(sticker ? "dialog.editTitle" : "dialog.newTitle")}</DialogTitle>
      </DialogHeader>
      <FieldGroup>
        {sticker ? null : <KindPicker kind={draft.kind} onChange={(kind) => setDraft({ ...draft, kind })} />}
        <Field data-invalid={nameInvalid}>
          <FieldLabel htmlFor={nameId}>{t("dialog.name")}</FieldLabel>
          <Input
            id={nameId}
            value={draft.name}
            maxLength={STICKER_NAME_MAX}
            dir="auto"
            placeholder={t("dialog.namePlaceholder")}
            aria-invalid={nameInvalid}
            onChange={(event) => setDraft({ ...draft, name: event.currentTarget.value })}
          />
        </Field>
        {draft.kind === "states" ? (
          <Field>
            <FieldLabel>{t("dialog.states")}</FieldLabel>
            <StatesEditor states={draft.states} onChange={(states) => setDraft({ ...draft, states })} />
          </Field>
        ) : null}
        {tried && problem ? <FieldError>{t(`problems.${problem}`, { max: STATES_MAX })}</FieldError> : null}
        {clears > 0 ? <p className="text-muted-foreground text-sm">{t("dialog.clears", { count: clears })}</p> : null}
      </FieldGroup>
      <DialogFooter className="sm:justify-between">
        {sticker ? <DeleteFieldButton sticker={sticker} owned={owned} onDeleted={onDone} /> : <span />}
        <Button type="submit" disabled={saving}>
          {saving ? <Spinner data-icon="inline-start" /> : null}
          {tc(sticker ? "actions.save" : "actions.create")}
        </Button>
      </DialogFooter>
    </form>
  );
}

/** Диалог поля: открывается запросом, закрывается после сохранения. */
export function FieldDialog({ request, onClose }: { request: FieldRequest | null; onClose: () => void }) {
  const sticker = request?.mode === "edit" ? request.sticker : null;
  return (
    <Dialog open={request !== null} onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="sm:max-w-md">
        {request ? <FieldForm key={sticker?.id ?? "new"} sticker={sticker} onDone={onClose} /> : null}
      </DialogContent>
    </Dialog>
  );
}
