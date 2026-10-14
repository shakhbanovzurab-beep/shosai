import { useState, useTransition } from "react";

import { useFormatter, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { InputOTP, InputOTPGroup, InputOTPSlot } from "@/components/ui/input-otp";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { useRouter } from "@/lib/navigation";

import type { Refusal } from "../model/outcome";
import { confirmRegistration, resendCode } from "../model/registration";
import { useCountdown } from "../model/use-countdown";
import { ProblemMessage } from "./problem-message";
import type { StartedRegistration } from "./register-form";

const CODE_LENGTH = 6;
const SLOTS = [0, 1, 2, 3, 4, 5] as const;

/** Код из письма: шесть цифр подтверждают почту, заводят аккаунт и открывают кабинет. */
export function VerifyForm({
  registration,
  next,
  onBack,
}: {
  registration: StartedRegistration;
  next: string;
  onBack: () => void;
}) {
  const t = useTranslations("identityRegistration");
  const format = useFormatter();
  const router = useRouter();
  const [code, setCode] = useState("");
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [resent, setResent] = useState(false);
  const [pending, startTransition] = useTransition();
  const { remaining, restart } = useCountdown(registration.resendAfterSeconds);

  const confirm = (value: string) => {
    startTransition(async () => {
      const outcome = await confirmRegistration(registration.registrationId, value);
      if (outcome.kind === "done") {
        router.replace(next);
        return;
      }
      setRefusal(outcome);
      setCode("");
    });
  };

  const resend = () => {
    startTransition(async () => {
      const outcome = await resendCode(registration.registrationId);
      setResent(outcome.kind === "done");
      if (outcome.kind === "done") {
        setRefusal(null);
        restart(outcome.value.resend_after_seconds);
      } else {
        setRefusal(outcome);
        if (outcome.retryAfterSeconds !== null) restart(outcome.retryAfterSeconds);
      }
    });
  };

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (code.length === CODE_LENGTH) confirm(code);
      }}
    >
      <div className="flex flex-col gap-2">
        <Label htmlFor="registration-code">{t("verify.code")}</Label>
        {/* Код — цифры слева направо в любом языке. */}
        <div dir="ltr">
          <InputOTP
            id="registration-code"
            maxLength={CODE_LENGTH}
            inputMode="numeric"
            pattern="^[0-9]*$"
            autoComplete="one-time-code"
            autoFocus
            value={code}
            disabled={pending}
            onChange={setCode}
            onComplete={confirm}
          >
            <InputOTPGroup>
              {SLOTS.map((slot) => (
                <InputOTPSlot key={slot} index={slot} className="size-11 text-lg" />
              ))}
            </InputOTPGroup>
          </InputOTP>
        </div>
      </div>
      {refusal === null ? null : <ProblemMessage refusal={refusal} />}
      {resent && refusal === null ? (
        <p aria-live="polite" className="text-muted-foreground text-sm">
          {t("verify.resent")}
        </p>
      ) : null}
      <Button type="submit" size="lg" disabled={pending || code.length !== CODE_LENGTH}>
        {pending ? <Spinner data-icon="inline-start" /> : null}
        {t("verify.submit")}
      </Button>
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <Button type="button" variant="link" className="px-0" onClick={onBack}>
          {t("verify.back")}
        </Button>
        {remaining > 0 ? (
          <span className="text-muted-foreground">
            {t("verify.resendIn", { time: format.number(remaining, { style: "unit", unit: "second" }) })}
          </span>
        ) : (
          <Button type="button" variant="link" className="px-0" disabled={pending} onClick={resend}>
            {t("verify.resend")}
          </Button>
        )}
      </div>
    </form>
  );
}
