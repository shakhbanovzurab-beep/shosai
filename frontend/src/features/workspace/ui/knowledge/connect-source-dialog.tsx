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
import { FieldDescription, FieldError, FieldLabel } from "@/components/ui/field-text";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

import { CONNECTOR_PROVIDERS, type ConnectorProvider } from "../../domain/knowledge-contract";
import { parseAccessKey } from "../../domain/visibility";
import { connectSource } from "../../model/knowledge-actions";
import { useWorkspace } from "../../model/use-workspace";
import { AccessField } from "./access-field";
import { KnowledgeIcon } from "./knowledge-icon";

// Example links, the same in every language.
const PLACEHOLDERS: Record<ConnectorProvider, string> = {
  drive: "https://drive.google.com/drive/folders/…",
  notion: "https://notion.so/your-team/…",
  confluence: "https://your-team.atlassian.net/wiki/spaces/…",
  web: "https://docs.your-company.com",
};

/** Mounted per opening, so each connection starts empty. */
function ConnectSourceForm({ onDone }: { onDone: () => void }) {
  const { ws, state } = useWorkspace();
  const t = useTranslations("workspaceKnowledgeDialogs");
  const words = useTranslations("workspaceKnowledge");
  const common = useTranslations("common");
  const [provider, setProvider] = useState<ConnectorProvider>("drive");
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [access, setAccess] = useState("workspace");
  const [error, setError] = useState<string | null>(null);

  const [, submit, pending] = useActionState(async () => {
    const failure = await connectSource(ws, {
      provider,
      // A source left unnamed is called after its provider, in the interface language ("Website").
      name: name.trim() || words(`kind.${provider}`),
      url: url.trim() || null,
      access: parseAccessKey(access),
    });
    if (failure) setError(failure);
    else onDone();
    return null;
  }, null);

  return (
    <form action={submit} noValidate className="flex flex-col gap-4">
      <DialogHeader>
        <DialogTitle>{t("connect.title")}</DialogTitle>
        <DialogDescription>{t("connect.description", { workspace: state.workspace.name })}</DialogDescription>
      </DialogHeader>
      <FieldGroup>
        <Field>
          <FieldLabel id="source-provider-label">{t("connect.source")}</FieldLabel>
          <ToggleGroup
            type="single"
            variant="outline"
            value={provider}
            onValueChange={(next) => next && setProvider(next as ConnectorProvider)}
            aria-labelledby="source-provider-label"
            className="flex-wrap justify-start"
          >
            {CONNECTOR_PROVIDERS.map((p) => (
              <ToggleGroupItem key={p} value={p} className="gap-2">
                <KnowledgeIcon kind={p} size="sm" />
                {words(`kind.${p}`)}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </Field>
        <Field>
          <FieldLabel htmlFor="source-url">{t("connect.link")}</FieldLabel>
          <Input
            id="source-url"
            type="url"
            // A link reads left to right in every language.
            dir="ltr"
            inputMode="url"
            autoComplete="off"
            spellCheck={false}
            placeholder={PLACEHOLDERS[provider]}
            value={url}
            onChange={(event) => setUrl(event.target.value)}
          />
          <FieldDescription>{t("connect.linkHint")}</FieldDescription>
        </Field>
        <Field>
          <FieldLabel htmlFor="source-name">{common("fields.name")}</FieldLabel>
          <Input
            id="source-name"
            autoComplete="off"
            dir="auto"
            placeholder={words(`kind.${provider}`)}
            maxLength={120}
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </Field>
        <AccessField id="source-access" value={access} onChange={setAccess} />
        {error ? <FieldError role="alert">{error}</FieldError> : null}
      </FieldGroup>
      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onDone}>
          {common("actions.cancel")}
        </Button>
        <Button type="submit" disabled={pending}>
          {pending ? <Spinner data-icon="inline-start" /> : null}
          {t("connect.submit")}
        </Button>
      </DialogFooter>
    </form>
  );
}

export function ConnectSourceDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        {open ? <ConnectSourceForm onDone={() => onOpenChange(false)} /> : null}
      </DialogContent>
    </Dialog>
  );
}
