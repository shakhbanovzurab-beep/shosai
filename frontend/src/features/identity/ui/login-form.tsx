import { useActionState, useState } from "react";

import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Link, useRouter } from "@/lib/navigation";

import { authPathFor, FORGOT_PATH } from "../domain/next-path";
import type { Outcome } from "../model/outcome";
import { signIn } from "../model/sign-in";
import { Captcha } from "./captcha";
import { ProblemMessage } from "./problem-message";

interface Attempt {
  outcome: Outcome<void> | null;
  // React сбрасывает форму после действия: почта возвращается в поле отсюда, пароль вводится заново.
  email: string;
  // После первого отказа капчи она остаётся на форме: сервер просит её до конца окна неудач.
  captcha: boolean;
  count: number;
}

const FIRST: Attempt = { outcome: null, email: "", captcha: false, count: 0 };

/** Почта и пароль; после успеха — страница, с которой человека отправили на вход. */
export function LoginForm({ next }: { next: string }) {
  const t = useTranslations("identity");
  const router = useRouter();
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [attempt, submit, pending] = useActionState(async (previous: Attempt, form: FormData): Promise<Attempt> => {
    const email = String(form.get("email") ?? "").trim();
    const outcome = await signIn({ email, password: String(form.get("password") ?? ""), captchaToken });
    if (outcome.kind === "done") router.replace(next);
    // Токен проверки одноразовый: следующая попытка получит новый.
    setCaptchaToken(null);
    const refused = outcome.kind === "refused" && outcome.problem === "captcha_failed";
    return { outcome, email, captcha: previous.captcha || refused, count: previous.count + 1 };
  }, FIRST);
  const waitsForCaptcha = attempt.captcha && captchaToken === null;

  return (
    <form action={submit} className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <Label htmlFor="sign-in-email">{t("signIn.email")}</Label>
        <Input
          id="sign-in-email"
          name="email"
          type="email"
          autoComplete="email"
          defaultValue={attempt.email}
          required
          autoFocus
          dir="ltr"
        />
      </div>
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
          <Label htmlFor="sign-in-password">{t("signIn.password")}</Label>
          <Link href={authPathFor(FORGOT_PATH, next)} className="text-muted-foreground text-sm hover:text-foreground">
            {t("signIn.forgot")}
          </Link>
        </div>
        <Input id="sign-in-password" name="password" type="password" autoComplete="current-password" required />
      </div>
      {attempt.captcha ? <Captcha key={attempt.count} onToken={setCaptchaToken} /> : null}
      {attempt.outcome?.kind === "refused" ? <ProblemMessage refusal={attempt.outcome} /> : null}
      <Button type="submit" size="lg" disabled={pending || waitsForCaptcha}>
        {pending ? <Spinner data-icon="inline-start" /> : null}
        {t("signIn.submit")}
      </Button>
    </form>
  );
}
