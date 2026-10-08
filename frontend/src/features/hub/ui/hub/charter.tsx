"use client";

import { useId, useState } from "react";

import { Plus } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { FieldDescription, FieldLabel } from "@/components/ui/field-text";
import { Textarea } from "@/components/ui/textarea";

import { CHARTER_MAX, type Hub } from "../../domain/contract";
import { saveCharter } from "../../model/hub-actions";
import { useHubWords } from "../../model/words";
import { SubmitButton } from "../shared/submit-button";

/** The two fields, in the person's words only: no drafts, no suggestions, no examples to accept. */
function CharterForm({ hub, onDone }: { hub: Hub; onDone: () => void }) {
  const words = useHubWords();
  const t = useTranslations("hub");
  const common = useTranslations("common");
  const id = useId();
  // Controlled, so the words stay in place if saving fails.
  const [purpose, setPurpose] = useState(hub.purpose ?? "");
  const [success, setSuccess] = useState(hub.success ?? "");
  return (
    <form
      className="flex flex-col gap-4 rounded-lg border p-4"
      action={async () => {
        if (await saveCharter(words, hub, purpose, success)) onDone();
      }}
    >
      <Field>
        <FieldLabel htmlFor={`${id}-purpose`}>{t("page.purposeLabel")}</FieldLabel>
        <Textarea
          id={`${id}-purpose`}
          name="purpose"
          dir="auto"
          value={purpose}
          onChange={(event) => setPurpose(event.target.value)}
          maxLength={CHARTER_MAX}
          rows={2}
        />
      </Field>
      <Field>
        <FieldLabel htmlFor={`${id}-success`}>{t("page.successLabel")}</FieldLabel>
        <Textarea
          id={`${id}-success`}
          name="success"
          dir="auto"
          value={success}
          onChange={(event) => setSuccess(event.target.value)}
          maxLength={CHARTER_MAX}
          rows={2}
        />
        <FieldDescription>{t("page.charterHint", { max: CHARTER_MAX })}</FieldDescription>
      </Field>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onDone}>
          {common("actions.cancel")}
        </Button>
        <SubmitButton>{common("actions.save")}</SubmitButton>
      </div>
    </form>
  );
}

/**
 * Why the hub exists and what counts as success: a quiet block. Empty, it is one quiet line that
 * invites a person to write it, never an empty form.
 */
export function Charter({ hub }: { hub: Hub }) {
  const t = useTranslations("hub");
  const [editing, setEditing] = useState(false);
  if (editing) return <CharterForm hub={hub} onDone={() => setEditing(false)} />;
  if (!hub.purpose && !hub.success)
    return (
      <Button
        variant="ghost"
        size="sm"
        className="-ms-2 w-fit max-w-full justify-start whitespace-normal border-transparent bg-transparent text-start text-muted-foreground"
        onClick={() => setEditing(true)}
      >
        <Plus data-icon="inline-start" aria-hidden="true" />
        {t("page.charterInvite")}
      </Button>
    );
  return (
    <div className="flex items-start justify-between gap-4 text-sm">
      <dl className="flex min-w-0 flex-col gap-1">
        {[
          [t("page.why"), hub.purpose],
          [t("page.success"), hub.success],
        ].map(([term, text]) =>
          text ? (
            <div key={term} className="flex gap-2">
              <dt className="shrink-0 text-muted-foreground">{term}</dt>
              <dd className="min-w-0 text-pretty" dir="auto">
                {text}
              </dd>
            </div>
          ) : null,
        )}
      </dl>
      <Button
        variant="ghost"
        size="xs"
        className="shrink-0 border-transparent bg-transparent text-muted-foreground"
        onClick={() => setEditing(true)}
      >
        {t("page.edit")}
      </Button>
    </div>
  );
}
