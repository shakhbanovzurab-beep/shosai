"use client";

import { useId, useState } from "react";

import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

import { addLink } from "../../model/material-actions";
import { useHubWords } from "../../model/words";
import { SubmitButton } from "../shared/submit-button";

/** The form, mounted with the dialog: empty each time it opens; a refused link stays for fixing. */
function LinkForm({ hubId, onDone }: { hubId: string; onDone: () => void }) {
  const words = useHubWords();
  const t = useTranslations("hubBlocks");
  const common = useTranslations("common");
  const id = useId();
  const [title, setTitle] = useState("");
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  return (
    <form
      className="flex flex-col gap-5"
      action={async () => {
        const problem = await addLink(words, hubId, title, url);
        if (problem) setError(problem);
        else onDone();
      }}
    >
      <DialogHeader>
        <DialogTitle>{t("materials.addTitle")}</DialogTitle>
      </DialogHeader>
      <Field>
        <FieldLabel htmlFor={`${id}-title`}>{t("materials.titleLabel")}</FieldLabel>
        <Input
          id={`${id}-title`}
          name="title"
          dir="auto"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          required
          maxLength={200}
          autoComplete="off"
        />
      </Field>
      <Field data-invalid={error !== null}>
        <FieldLabel htmlFor={`${id}-url`}>{t("materials.urlLabel")}</FieldLabel>
        <Input
          id={`${id}-url`}
          name="url"
          type="url"
          inputMode="url"
          required
          // i18n-ignore: a URL scheme, the same in every language.
          placeholder="https://"
          value={url}
          aria-invalid={error !== null}
          onChange={(event) => {
            setUrl(event.target.value);
            setError(null);
          }}
        />
        {error ? <FieldError>{error}</FieldError> : null}
      </Field>
      <DialogFooter>
        <DialogClose asChild>
          <Button type="button" variant="outline">
            {common("actions.cancel")}
          </Button>
        </DialogClose>
        <SubmitButton>{common("actions.add")}</SubmitButton>
      </DialogFooter>
    </form>
  );
}

/** Adds a link to a document or a file kept elsewhere. */
export function AddLinkDialog({
  hubId,
  open,
  onOpenChange,
}: {
  hubId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <LinkForm hubId={hubId} onDone={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}
