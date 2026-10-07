"use client";

import { useActionState } from "react";

import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
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

import { type ConnectorDefinition, type ConnectorField, hasHelp } from "../domain/connectors";
import type { Connector } from "../domain/contract";
import { connectSource } from "../model/connector-actions";
import type { SourceWords } from "../model/words";
import { ConnectorIcon } from "./connector-icon";
import { useConnectorName } from "./connector-name";

function Field({ field, saved }: { field: ConnectorField; saved?: string }) {
  const t = useTranslations("knowledgeBaseSources");
  const id = `connector-${field.key}`;
  const help = hasHelp(field.key) ? t(`help.${field.key}`) : null;
  const shared = {
    id,
    name: field.key,
    required: field.required,
    // Examples are identifiers, paths, URLs or query syntax, written the same in every language.
    placeholder: field.example,
    defaultValue: saved,
    dir: "auto",
    "aria-describedby": help ? `${id}-help` : undefined,
  };
  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={id}>
        {t(`fields.${field.key}`)}
        {field.required ? null : <span className="font-normal text-muted-foreground">{t("dialog.optional")}</span>}
      </Label>
      {field.type === "textarea" ? <Textarea {...shared} rows={3} /> : <Input {...shared} type={field.type} />}
      {help ? (
        <p id={`${id}-help`} className="text-muted-foreground text-xs">
          {help}
        </p>
      ) : null}
    </div>
  );
}

function submitLabel(definition: ConnectorDefinition, name: string, isEdit: boolean, t: SourceWords) {
  if (isEdit) return t("dialog.saveAndSync");
  return definition.auth === "oauth"
    ? t("dialog.continueWith", { provider: definition.provider ?? name })
    : t("dialog.connect");
}

type ConnectorDialogProps = {
  definition: ConnectorDefinition | null;
  connector: Connector | null;
  onClose: () => void;
};

/** Connect a source, or change its settings. OAuth sources hand off to the provider when the backend asks. */
export function ConnectorDialog({ definition, connector, onClose }: ConnectorDialogProps) {
  const t = useTranslations("knowledgeBaseSources");
  const common = useTranslations("common");
  const nameOf = useConnectorName();
  const name = definition ? nameOf(definition) : "";
  const [error, submit, pending] = useActionState(async (_prev: string | null, form: FormData) => {
    if (!definition) return null;
    const config = Object.fromEntries(definition.fields.map((f) => [f.key, String(form.get(f.key) ?? "").trim()]));
    const result = await connectSource(definition, name, config, t);
    if (result.status === "failed") return result.message;
    if (result.status === "connected") onClose();
    return null;
  }, null);

  const isEdit = connector !== null && connector.status !== "disconnected";

  return (
    <Dialog open={definition !== null} onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="sm:max-w-md">
        {definition ? (
          <form action={submit} className="flex flex-col gap-5">
            <DialogHeader className="flex-row items-center gap-3">
              <ConnectorIcon id={definition.id} />
              <div className="flex flex-col gap-1 text-start">
                <DialogTitle>{t(isEdit ? "dialog.settingsTitle" : "dialog.connectTitle", { name })}</DialogTitle>
                <DialogDescription>{t(`descriptions.${definition.id}`)}</DialogDescription>
              </div>
            </DialogHeader>
            {definition.auth === "oauth" ? (
              <p className="rounded-lg border bg-muted/50 p-3 text-muted-foreground text-sm">
                {t("dialog.oauthNote", { provider: definition.provider ?? name })}
              </p>
            ) : null}
            {definition.fields.map((field) => (
              <Field key={field.key} field={field} saved={connector?.config[field.key]} />
            ))}
            {error ? (
              <p role="alert" className="text-destructive text-sm" dir="auto">
                {error}
              </p>
            ) : null}
            <DialogFooter>
              <DialogClose asChild>
                <Button type="button" variant="outline">
                  {common("actions.cancel")}
                </Button>
              </DialogClose>
              <Button type="submit" disabled={pending}>
                {pending ? <Spinner data-icon="inline-start" /> : null}
                {submitLabel(definition, name, isEdit, t)}
              </Button>
            </DialogFooter>
          </form>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
