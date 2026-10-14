import { useId, useState, useTransition } from "react";

import { useLocale, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";

import { consentsBody, consentsComplete, NO_CONSENTS } from "../domain/consents";
import { type CountryCode, countryFromLanguages, needsCrossBorderConsent } from "../domain/countries";
import { PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH } from "../domain/password-rules";
import type { Refusal } from "../model/outcome";
import { register } from "../model/registration";
import { turnstileSiteKey } from "../model/turnstile-host";
import { Captcha } from "./captcha";
import { ConsentChecks } from "./consent-checks";
import { CountryField } from "./country-field";
import { PasswordStrength } from "./password-strength";
import { ProblemMessage } from "./problem-message";

export interface StartedRegistration {
  registrationId: string;
  email: string;
  resendAfterSeconds: number;
}

/** Имя, почта, пароль, страна и согласия; после отправки сервер присылает на почту код. */
export function RegisterForm({ onStarted }: { onStarted: (registration: StartedRegistration) => void }) {
  const t = useTranslations("identityRegistration");
  const language = useLocale();
  const id = useId();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [country, setCountry] = useState<CountryCode | null>(() => countryFromLanguages(navigator.languages));
  const [consents, setConsents] = useState(NO_CONSENTS);
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [captchaRound, setCaptchaRound] = useState(0);
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [pending, startTransition] = useTransition();
  const crossBorder = needsCrossBorderConsent(country);
  const waitsForCaptcha = turnstileSiteKey() !== null && captchaToken === null;

  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (country === null) return;
    startTransition(async () => {
      const outcome = await register({
        email: email.trim(),
        password,
        full_name: name.trim(),
        country,
        language,
        consents: consentsBody(consents, crossBorder),
        captcha_token: captchaToken,
      });
      // Токен проверки одноразовый: и после успеха (человек может вернуться сменить почту), и после отказа
      // следующая попытка получит новый.
      setCaptchaToken(null);
      setCaptchaRound((round) => round + 1);
      if (outcome.kind === "done") {
        const { registration_id, resend_after_seconds } = outcome.value;
        setRefusal(null);
        onStarted({ registrationId: registration_id, email: email.trim(), resendAfterSeconds: resend_after_seconds });
        return;
      }
      setRefusal(outcome);
    });
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <Label htmlFor={`${id}-name`}>{t("name")}</Label>
        <Input
          id={`${id}-name`}
          autoComplete="name"
          required
          maxLength={80}
          autoFocus
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor={`${id}-email`}>{t("email")}</Label>
        <Input
          id={`${id}-email`}
          type="email"
          autoComplete="email"
          required
          dir="ltr"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor={`${id}-password`}>{t("password")}</Label>
        <Input
          id={`${id}-password`}
          type="password"
          autoComplete="new-password"
          required
          minLength={PASSWORD_MIN_LENGTH}
          maxLength={PASSWORD_MAX_LENGTH}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <PasswordStrength password={password} />
      </div>
      <CountryField id={`${id}-country`} value={country} onChange={setCountry} />
      <ConsentChecks id={id} value={consents} crossBorder={crossBorder} onChange={setConsents} />
      {turnstileSiteKey() === null ? null : <Captcha key={captchaRound} onToken={setCaptchaToken} />}
      {refusal === null ? null : <ProblemMessage refusal={refusal} />}
      <Button type="submit" size="lg" disabled={pending || waitsForCaptcha || !consentsComplete(consents, crossBorder)}>
        {pending ? <Spinner data-icon="inline-start" /> : null}
        {t("submit")}
      </Button>
    </form>
  );
}
