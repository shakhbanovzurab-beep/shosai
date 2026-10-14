import { useTranslations } from "use-intl";

import { Link } from "@/lib/navigation";

import { authPathFor, REGISTER_PATH } from "../domain/next-path";
import type { Refusal } from "../model/outcome";
import { AuthHeading } from "./auth-heading";
import { LoginForm } from "./login-form";
import { ProblemMessage } from "./problem-message";
import { SocialButtons } from "./social-buttons";

/**
 * Вход: почта и пароль, быстрый вход через сервис и путь к регистрации. `socialRefusal` — причина, с которой
 * сервис вернул человека обратно.
 */
export function LoginPanel({ next, socialRefusal }: { next: string; socialRefusal: Refusal | null }) {
  const t = useTranslations("identity");
  return (
    <>
      <AuthHeading title={t("signIn.title")}>{t("signIn.description")}</AuthHeading>
      <div className="flex flex-col gap-6">
        {socialRefusal === null ? null : <ProblemMessage refusal={socialRefusal} />}
        <LoginForm next={next} />
        <SocialButtons next={next} />
        <p className="text-center text-muted-foreground text-sm">
          {t("signIn.noAccount")}{" "}
          <Link
            href={authPathFor(REGISTER_PATH, next)}
            className="font-medium text-foreground underline-offset-4 hover:underline"
          >
            {t("signIn.register")}
          </Link>
        </p>
      </div>
    </>
  );
}
