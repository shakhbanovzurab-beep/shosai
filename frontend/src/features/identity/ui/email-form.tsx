import { useActionState, useState } from "react";

import { useLocale, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";

import type { Outcome } from "../model/outcome";
import { type CodeSent, sendCode } from "../model/passwordless";
import { Captcha } from "./captcha";
import { ProblemMessage } from "./problem-message";

export interface SentTo extends CodeSent {
  email: string;
}

interface Attempt {
  outcome: Outcome<CodeSent> | null;
  // React сбрасывает форму после действия: адрес возвращается в поле отсюда.
  email: string;
  // После отказа проверки она остаётся на форме: сервер просит её до конца окна неудач.
  captcha: boolean;
  count: number;
}

const FIRST: Attempt = { outcome: null, email: "", captcha: false, count: 0 };

/** Почта и кнопка «Продолжить»: сервер присылает код; один путь и для входа, и для нового аккаунта. */
export function EmailForm({ next, onSent }: { next: string; onSent: (sent: SentTo) => void }) {
  const t = useTranslations("identity");
  const language = useLocale();
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [attempt, submit, pending] = useActionState(async (previous: Attempt, form: FormData): Promise<Attempt> => {
    const email = String(form.get("email") ?? "").trim();
    const outcome = await sendCode({ email, language, next, captchaToken });
    // Токен проверки одноразовый: следующая попытка получит новый.
    setCaptchaToken(null);
    if (outcome.kind === "done") onSent({ ...outcome.value, email });
    const refused = outcome.kind === "refused" && outcome.problem === "captcha_failed";
    return { outcome, email, captcha: previous.captcha || refused, count: previous.count + 1 };
  }, FIRST);

  return (
    <form action={submit} className="flex flex-col gap-3">
      <Input
        name="email"
        type="email"
        autoComplete="email"
        aria-label={t("signIn.email")}
        placeholder={t("signIn.emailPlaceholder")}
        defaultValue={attempt.email}
        required
        dir="ltr"
        className="h-11"
      />
      {attempt.captcha ? <Captcha key={attempt.count} onToken={setCaptchaToken} /> : null}
      {attempt.outcome?.kind === "refused" ? <ProblemMessage refusal={attempt.outcome} /> : null}
      <Button type="submit" size="lg" className="h-11" disabled={pending || (attempt.captcha && captchaToken === null)}>
        {pending ? <Spinner data-icon="inline-start" /> : null}
        {t("signIn.continueWithEmail")}
      </Button>
    </form>
  );
}
