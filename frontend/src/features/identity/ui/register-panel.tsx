import { Activity, useState } from "react";

import { useTranslations } from "use-intl";

import { Link } from "@/lib/navigation";

import { authPathFor, LOGIN_PATH } from "../domain/next-path";
import { AuthHeading } from "./auth-heading";
import { RegisterForm, type StartedRegistration } from "./register-form";
import { VerifyForm } from "./verify-form";

/**
 * Регистрация в два шага: форма, затем код из письма; аккаунт появляется только после кода. Форма на втором шаге
 * спрятана, а не снята, — «другая почта» возвращает её заполненной.
 */
export function RegisterPanel({ next }: { next: string }) {
  const t = useTranslations("identityRegistration");
  const [started, setStarted] = useState<StartedRegistration | null>(null);

  return (
    <>
      {started === null ? null : (
        <>
          <AuthHeading title={t("verify.title")}>{t("verify.description", { email: started.email })}</AuthHeading>
          <VerifyForm registration={started} next={next} onBack={() => setStarted(null)} />
        </>
      )}
      <Activity mode={started === null ? "visible" : "hidden"}>
        <AuthHeading title={t("title")}>{t("description")}</AuthHeading>
        <div className="flex flex-col gap-6">
          <RegisterForm onStarted={setStarted} />
          <p className="text-center text-muted-foreground text-sm">
            {t("haveAccount")}{" "}
            <Link
              href={authPathFor(LOGIN_PATH, next)}
              className="font-medium text-foreground underline-offset-4 hover:underline"
            >
              {t("signIn")}
            </Link>
          </p>
        </div>
      </Activity>
    </>
  );
}
