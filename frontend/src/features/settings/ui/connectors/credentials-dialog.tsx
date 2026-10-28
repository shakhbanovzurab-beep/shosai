"use client";

import { type ReactNode, useActionState } from "react";

import { useTranslations } from "use-intl";

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
import { Field, FieldGroup } from "@/components/ui/field";
import { FieldError, FieldLabel } from "@/components/ui/field-text";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";

import { credentialsFrom, needsAddress } from "../../domain/connector-credentials";
import type { Connector } from "../../domain/connectors-contract";
import { connectWithCredentials } from "../../model/connector-actions";

function SecretFields({ connector }: { connector: Connector }) {
  const t = useTranslations("settingsConnectors");
  if (connector.auth === "api_key") {
    return (
      <Field>
        <FieldLabel htmlFor="connector-api-key">{t("credentials.apiKey")}</FieldLabel>
        <Input
          id="connector-api-key"
          spellCheck={false}
          name="api_key"
          type="password"
          autoComplete="off"
          required
          dir="auto"
        />
      </Field>
    );
  }
  if (connector.auth === "webhook") {
    return (
      <Field>
        <FieldLabel htmlFor="connector-webhook">{t("credentials.webhookUrl")}</FieldLabel>
        <Input
          id="connector-webhook"
          spellCheck={false}
          name="webhook_url"
          type="url"
          autoComplete="off"
          required
          dir="ltr"
        />
      </Field>
    );
  }
  return (
    <>
      {needsAddress(connector) ? (
        <Field>
          <FieldLabel htmlFor="connector-address">{t("credentials.address")}</FieldLabel>
          <Input
            id="connector-address"
            spellCheck={false}
            name="address"
            type="url"
            autoComplete="url"
            required
            dir="ltr"
          />
        </Field>
      ) : null}
      <Field>
        <FieldLabel htmlFor="connector-login">{t("credentials.login")}</FieldLabel>
        <Input id="connector-login" spellCheck={false} name="login" autoComplete="username" required dir="auto" />
      </Field>
      <Field>
        <FieldLabel htmlFor="connector-password">{t("credentials.password")}</FieldLabel>
        <Input id="connector-password" name="password" type="password" autoComplete="off" required dir="auto" />
      </Field>
    </>
  );
}

function CredentialsForm({ connector, onClose }: { connector: Connector; onClose: () => void }) {
  const t = useTranslations("settingsConnectors");
  const common = useTranslations("common");
  const [error, submit, pending] = useActionState(async (_prev: ReactNode | null, form: FormData) => {
    const failure = await connectWithCredentials(
      connector,
      credentialsFrom(connector, (name) => String(form.get(name) ?? "")),
      t,
    );
    if (failure === null) onClose();
    return failure;
  }, null);

  return (
    <form action={submit} className="flex flex-col gap-6">
      <DialogHeader>
        <DialogTitle>{t("credentials.title", { name: connector.name })}</DialogTitle>
        <DialogDescription>
          {t(`credentials.hint.${connector.auth === "oauth" ? "password" : connector.auth}`)}
        </DialogDescription>
      </DialogHeader>
      <FieldGroup>
        <SecretFields connector={connector} />
        {error ? <FieldError>{error}</FieldError> : null}
      </FieldGroup>
      <DialogFooter>
        <DialogClose asChild>
          <Button type="button" variant="ghost">
            {common("actions.cancel")}
          </Button>
        </DialogClose>
        <Button type="submit" disabled={pending}>
          {pending ? <Spinner data-icon="inline-start" /> : null}
          {t("connect")}
        </Button>
      </DialogFooter>
    </form>
  );
}

/** Connects an app by an app password, an API key or a hook URL; the secret is checked before it is kept. */
export function CredentialsDialog({ connector, onClose }: { connector: Connector | null; onClose: () => void }) {
  return (
    <Dialog open={connector !== null} onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="sm:max-w-md">
        {connector ? <CredentialsForm key={connector.id} connector={connector} onClose={onClose} /> : null}
      </DialogContent>
    </Dialog>
  );
}
