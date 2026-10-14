import { useState, useTransition } from "react";

import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Link } from "@/lib/navigation";

import { authPathFor, LOGIN_PATH } from "../domain/next-path";
import type { Refusal } from "../model/outcome";
import { askForResetLink } from "../model/password-recovery";
import { turnstileSiteKey } from "../model/turnstile-host";
import { AuthHeading } from "./auth-heading";
import { Captcha } from "./captcha";
import { ProblemMessage } from "./problem-message";

/** Забытый пароль: почта — и ссылка на новый пароль в письме. Ответ один, есть такой аккаунт или нет. */
export function ForgotPanel({ next }: { next: string }) {
  const t = useTranslations("identityRecovery");
  const [email, setEmail] = useState("");
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [captchaRound, setCaptchaRound] = useState(0);
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [pending, startTransition] = useTransition();
  const back = (
    <Link
      href={authPathFor(LOGIN_PATH, next)}
      className="text-center font-medium text-sm underline-offset-4 hover:underline"
    >
      {t("forgot.back")}
    </Link>
  );

  if (sentTo !== null) {
    return (
      <>
        <AuthHeading title={t("forgot.sentTitle")}>{t("forgot.sent", { email: sentTo })}</AuthHeading>
        {back}
      </>
    );
  }

  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    startTransition(async () => {
      const outcome = await askForResetLink(email.trim(), captchaToken);
      setCaptchaToken(null);
      setCaptchaRound((round) => round + 1);
      if (outcome.kind === "done") setSentTo(email.trim());
      else setRefusal(outcome);
    });
  };

  return (
    <>
      <AuthHeading title={t("forgot.title")}>{t("forgot.description")}</AuthHeading>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <Label htmlFor="forgot-email">{t("forgot.email")}</Label>
          <Input
            id="forgot-email"
            type="email"
            autoComplete="email"
            required
            autoFocus
            dir="ltr"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>
        {turnstileSiteKey() === null ? null : <Captcha key={captchaRound} onToken={setCaptchaToken} />}
        {refusal === null ? null : <ProblemMessage refusal={refusal} />}
        <Button type="submit" size="lg" disabled={pending || (turnstileSiteKey() !== null && captchaToken === null)}>
          {pending ? <Spinner data-icon="inline-start" /> : null}
          {t("forgot.submit")}
        </Button>
        {back}
      </form>
    </>
  );
}
