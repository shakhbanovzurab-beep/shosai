"use client";

import { useId, useState } from "react";

import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { FieldDescription, FieldError, FieldLabel } from "@/components/ui/field-text";
import { Input } from "@/components/ui/input";

import { HUB_NAME_MAX, HUB_NAME_MIN, type Hub } from "../../domain/contract";
import { createHub, renameHub } from "../../model/hub-actions";
import { errorText, useHubWords } from "../../model/words";
import { SubmitButton } from "../shared/submit-button";

/** The form, mounted with the dialog: it starts from the hub's name (or empty) every time it opens. */
function NameForm({ hub, onDone, onCreated }: { hub: Hub | null; onDone: () => void; onCreated?: (hub: Hub) => void }) {
  const words = useHubWords();
  const t = useTranslations("hub");
  const common = useTranslations("common");
  const id = useId();
  // Controlled, so a refused name stays in the field for the person to fix.
  const [name, setName] = useState(hub?.name ?? "");
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    const clean = name.trim().replace(/\s+/g, " ");
    if (clean.length < HUB_NAME_MIN) return setError(errorText(words.api, "name_too_short"));
    if (clean.length > HUB_NAME_MAX) return setError(errorText(words.api, "name_too_long"));
    const outcome = hub ? await renameHub(words, hub, clean) : await createHub(words, clean);
    if (!outcome.ok) return setError(errorText(words.api, outcome.code));
    onDone();
    if (!hub) onCreated?.(outcome.hub);
  }

  return (
    <form className="flex flex-col gap-5" action={submit} noValidate>
      <DialogHeader>
        <DialogTitle>{hub ? t("form.renameTitle") : t("form.createTitle")}</DialogTitle>
      </DialogHeader>
      <Field data-invalid={error !== null}>
        <FieldLabel htmlFor={id}>{common("fields.name")}</FieldLabel>
        <Input
          id={id}
          name="name"
          value={name}
          placeholder={t("form.namePlaceholder")}
          maxLength={HUB_NAME_MAX + 20}
          autoComplete="off"
          dir="auto"
          aria-invalid={error !== null}
          aria-describedby={`${id}-hint`}
          onChange={(event) => {
            setName(event.target.value);
            setError(null);
          }}
        />
        <FieldDescription id={`${id}-hint`}>{t("form.nameHint")}</FieldDescription>
        {error ? <FieldError>{error}</FieldError> : null}
      </Field>
      <DialogFooter>
        <DialogClose asChild>
          <Button type="button" variant="outline">
            {common("actions.cancel")}
          </Button>
        </DialogClose>
        <SubmitButton>{hub ? common("actions.save") : common("actions.create")}</SubmitButton>
      </DialogFooter>
    </form>
  );
}

/**
 * Naming a hub: only a person names it. The field starts empty (or with the current name when
 * renaming); the placeholder is an example, never a suggested value.
 */
export function NameDialog({
  hub,
  open,
  onOpenChange,
  onCreated,
}: {
  hub: Hub | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated?: (hub: Hub) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <NameForm key={hub?.id ?? "new"} hub={hub} onDone={() => onOpenChange(false)} onCreated={onCreated} />
      </DialogContent>
    </Dialog>
  );
}
