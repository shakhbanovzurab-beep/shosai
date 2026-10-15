"use client";

import { useState, useTransition } from "react";

import { toast } from "sonner";
import { useFormatter, useLocale, useTranslations } from "use-intl";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { LOGIN_PATH } from "@/features/identity/domain/next-path";
import { deleteMyAccount } from "@/features/identity/model/account-deletion";
import type { Outcome } from "@/features/identity/model/outcome";
import { type Arrival, sendCode } from "@/features/identity/model/passwordless";
import { CodeForm } from "@/features/identity/ui/code-form";
import type { SentTo } from "@/features/identity/ui/email-form";
import { apiErrorDescription } from "@/lib/api/error-description";
import { useRouter } from "@/lib/navigation";

import { SettingsGroup, SettingsRow } from "../settings-row";
import { ConfirmEmailField } from "./confirm-email-field";

/**
 * Последнее в Account: удалить всё. Адрес набирается заново; удаление назначается на 7 дней, вход в это время его
 * отменяет. Если вход был давно, сервер просит подтвердить себя — кодом из письма прямо в этом окне.
 */
export function DeleteAccount({ email }: { email: string }) {
  const t = useTranslations("settings");
  const common = useTranslations("common");
  const format = useFormatter();
  const language = useLocale();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [mismatch, setMismatch] = useState(false);
  const [code, setCode] = useState<SentTo | null>(null);
  const [pending, startTransition] = useTransition();
  const matches = typed.trim().toLowerCase() === email.toLowerCase();

  const remove = () =>
    startTransition(async () => {
      const outcome = await deleteMyAccount(typed.trim());
      if (outcome.kind === "scheduled") {
        const date = format.dateTime(new Date(outcome.eraseAt), "long");
        toast.success(t("deleteAccount.scheduled", { date }));
        router.replace(LOGIN_PATH);
      } else if (outcome.kind === "mismatch") setMismatch(true);
      else if (outcome.kind === "reauthenticate") {
        const sent = await sendCode({ email, language, next: "", captchaToken: null });
        if (sent.kind === "done") setCode({ ...sent.value, email });
        else toast.error(t("deleteAccount.failed"));
      } else toast.error(t("deleteAccount.failed"), { description: apiErrorDescription(outcome.error) });
    });

  // Код подтверждён — вход свежий, удаление просится снова.
  const verified = (outcome: Outcome<Arrival>) => {
    if (outcome.kind !== "done") return;
    setCode(null);
    remove();
  };

  return (
    <SettingsGroup title={t("deleteAccount.group")}>
      <SettingsRow title={t("deleteAccount.title")} description={t("deleteAccount.description")}>
        <Button variant="destructive" onClick={() => setOpen(true)}>
          {t("deleteAccount.title")}
        </Button>
      </SettingsRow>
      <AlertDialog
        open={open}
        onOpenChange={(next) => {
          setOpen(next);
          if (!next) {
            setTyped("");
            setCode(null);
            setMismatch(false);
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("deleteAccount.confirmTitle")}</AlertDialogTitle>
            <AlertDialogDescription>
              {code ? t("deleteAccount.reauthenticate", { email }) : t("deleteAccount.confirmDescription")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          {code ? (
            <CodeForm sent={code} onArrival={verified} onBack={() => setCode(null)} />
          ) : (
            <ConfirmEmailField email={email} value={typed} mismatch={mismatch} onChange={setTyped} />
          )}
          <AlertDialogFooter>
            <AlertDialogCancel>{common("actions.cancel")}</AlertDialogCancel>
            {code ? null : (
              <Button variant="destructive" disabled={!matches || pending} onClick={remove}>
                {pending ? <Spinner data-icon="inline-start" /> : null}
                {t("deleteAccount.title")}
              </Button>
            )}
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </SettingsGroup>
  );
}
