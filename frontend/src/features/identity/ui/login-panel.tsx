import { useState } from "react";

import { useTranslations } from "use-intl";

import { useRouter } from "@/lib/navigation";

import type { SocialProvider } from "../domain/social-providers";
import type { Outcome, Refusal } from "../model/outcome";
import type { Arrival } from "../model/passwordless";
import { AuthHeading } from "./auth-heading";
import { CodeForm } from "./code-form";
import { ConsentPanel } from "./consent-panel";
import { EmailForm, type SentTo } from "./email-form";
import { ProblemMessage } from "./problem-message";
import { SocialButtons } from "./social/social-buttons";
import { TermsNote } from "./terms-note";

type Via = SocialProvider | "email";
type Step = { kind: "start" } | { kind: "code"; sent: SentTo } | { kind: "consent"; ticket: string; via: Via };

/**
 * Вход без пароля (ADR 0048): сервисы, затем «или почтой» — код из письма; новому человеку — один экран согласий.
 * `socialRefusal` — причина, с которой сервис вернул человека обратно.
 */
export function LoginPanel({ next, socialRefusal }: { next: string; socialRefusal: Refusal | null }) {
  const t = useTranslations("identity");
  const router = useRouter();
  const [step, setStep] = useState<Step>({ kind: "start" });
  // Отказ виджета на этой странице важнее причины, с которой сервис вернул человека по адресу.
  const [widgetRefusal, setRefusal] = useState<Refusal | null>(null);
  const refusal = widgetRefusal ?? socialRefusal;
  const restart = () => setStep({ kind: "start" });

  const arrived = (via: Via) => (outcome: Outcome<Arrival>) => {
    if (outcome.kind === "refused") {
      setRefusal(outcome);
      return;
    }
    if (outcome.value.kind === "signed-in") router.replace(outcome.value.next);
    else setStep({ kind: "consent", ticket: outcome.value.ticket, via });
  };

  if (step.kind === "consent") {
    return <ConsentPanel ticket={step.ticket} via={step.via} onBack={restart} />;
  }
  if (step.kind === "code") {
    return (
      <>
        <AuthHeading title={t("code.title")}>{t("code.description", { email: step.sent.email })}</AuthHeading>
        <CodeForm sent={step.sent} onArrival={arrived("email")} onBack={restart} />
      </>
    );
  }
  return (
    <>
      {/* Экран говорит сам за себя: заголовок нужен только читателю экрана. */}
      <h1 className="sr-only">{t("signIn.metaTitle")}</h1>
      <div className="flex flex-col gap-5">
        {refusal === null ? null : <ProblemMessage refusal={refusal} />}
        <SocialButtons next={next} onArrival={(outcome, provider) => arrived(provider)(outcome)} />
        <div className="flex flex-col gap-3">
          <EmailForm next={next} onSent={(sent) => setStep({ kind: "code", sent })} />
          <TermsNote />
        </div>
      </div>
    </>
  );
}
