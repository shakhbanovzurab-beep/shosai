import { useState, useTransition } from "react";

import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Link } from "@/lib/navigation";

import { FORGOT_PATH, LOGIN_PATH } from "../domain/next-path";
import { PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH } from "../domain/password-rules";
import type { Refusal } from "../model/outcome";
import { saveNewPassword } from "../model/password-recovery";
import { AuthHeading } from "./auth-heading";
import { PasswordStrength } from "./password-strength";
import { ProblemMessage } from "./problem-message";

const LINK = "text-center font-medium text-sm underline-offset-4 hover:underline";

/** Новый пароль по ссылке из письма; `token` — из адреса, без него ссылка негодна. */
export function ResetPanel({ token }: { token: string | null }) {
  const t = useTranslations("identityRecovery");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [pending, startTransition] = useTransition();
  const mismatch = confirm.length > 0 && confirm !== password;

  if (token === null) {
    return (
      <>
        <AuthHeading title={t("reset.title")}>{t("reset.missingToken")}</AuthHeading>
        <Link href={FORGOT_PATH} className={LINK}>
          {t("reset.requestNew")}
        </Link>
      </>
    );
  }
  if (done) {
    return (
      <>
        <AuthHeading title={t("reset.doneTitle")}>{t("reset.done")}</AuthHeading>
        <Button size="lg" asChild>
          <Link href={LOGIN_PATH}>{t("reset.signIn")}</Link>
        </Button>
      </>
    );
  }

  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (mismatch) return;
    startTransition(async () => {
      const outcome = await saveNewPassword(token, password);
      if (outcome.kind === "done") setDone(true);
      else setRefusal(outcome);
    });
  };

  return (
    <>
      <AuthHeading title={t("reset.title")}>{t("reset.description")}</AuthHeading>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <Label htmlFor="reset-password">{t("reset.password")}</Label>
          <Input
            id="reset-password"
            type="password"
            autoComplete="new-password"
            required
            autoFocus
            minLength={PASSWORD_MIN_LENGTH}
            maxLength={PASSWORD_MAX_LENGTH}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <PasswordStrength password={password} />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="reset-confirm">{t("reset.confirm")}</Label>
          <Input
            id="reset-confirm"
            type="password"
            autoComplete="new-password"
            required
            aria-invalid={mismatch}
            aria-describedby={mismatch ? "reset-mismatch" : undefined}
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
          />
          {mismatch ? (
            <p id="reset-mismatch" className="text-destructive text-sm">
              {t("reset.mismatch")}
            </p>
          ) : null}
        </div>
        {refusal === null ? null : <ProblemMessage refusal={refusal} />}
        {refusal?.problem === "invalid_token" ? (
          <Link href={FORGOT_PATH} className={LINK}>
            {t("reset.requestNew")}
          </Link>
        ) : null}
        <Button type="submit" size="lg" disabled={pending || mismatch}>
          {pending ? <Spinner data-icon="inline-start" /> : null}
          {t("reset.submit")}
        </Button>
      </form>
    </>
  );
}
