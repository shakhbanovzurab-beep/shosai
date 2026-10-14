import { useId, useState, useTransition } from "react";

import { useLocale, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { Link, useRouter } from "@/lib/navigation";

import { consentsBody, consentsComplete, NO_CONSENTS } from "../domain/consents";
import { type CountryCode, countryFromLanguages, needsCrossBorderConsent } from "../domain/countries";
import { LOGIN_PATH } from "../domain/next-path";
import { SOCIAL_PROVIDER_NAMES, type SocialProvider } from "../domain/social-providers";
import type { Refusal } from "../model/outcome";
import { registerThroughSocial } from "../model/social-sign-in";
import { AuthHeading } from "./auth-heading";
import { ConsentChecks } from "./consent-checks";
import { CountryField } from "./country-field";
import { ProblemMessage } from "./problem-message";

/**
 * Первый вход через сервис: сервис человека узнал, но аккаунта ещё нет. Страна и согласия — те же, что при
 * регистрации почтой; аккаунт появляется только после этого экрана.
 */
export function SocialConsentPanel({ ticket, provider }: { ticket: string; provider: SocialProvider }) {
  const t = useTranslations("identity");
  const language = useLocale();
  const router = useRouter();
  const id = useId();
  const [country, setCountry] = useState<CountryCode | null>(() => countryFromLanguages(navigator.languages));
  const [consents, setConsents] = useState(NO_CONSENTS);
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [pending, startTransition] = useTransition();
  const crossBorder = needsCrossBorderConsent(country);

  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (country === null) return;
    startTransition(async () => {
      const outcome = await registerThroughSocial({
        ticket,
        country,
        language,
        consents: consentsBody(consents, crossBorder),
      });
      if (outcome.kind === "done") router.replace(outcome.value);
      else setRefusal(outcome);
    });
  };

  return (
    <>
      <AuthHeading title={t("social.consentTitle")}>
        {t("social.consentDescription", { provider: SOCIAL_PROVIDER_NAMES[provider] })}
      </AuthHeading>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <CountryField id={`${id}-country`} value={country} onChange={setCountry} />
        <ConsentChecks id={id} value={consents} crossBorder={crossBorder} onChange={setConsents} />
        {refusal === null ? null : <ProblemMessage refusal={refusal} />}
        <Button
          type="submit"
          size="lg"
          disabled={pending || country === null || !consentsComplete(consents, crossBorder)}
        >
          {pending ? <Spinner data-icon="inline-start" /> : null}
          {t("social.consentSubmit")}
        </Button>
        <Link href={LOGIN_PATH} className="text-center font-medium text-sm underline-offset-4 hover:underline">
          {t("social.back")}
        </Link>
      </form>
    </>
  );
}
