import { useState, useTransition } from "react";

import { useFormatter, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { InputOTP, InputOTPGroup, InputOTPSlot } from "@/components/ui/input-otp";
import { Spinner } from "@/components/ui/spinner";

import type { Outcome, Refusal } from "../model/outcome";
import { type Arrival, confirmCode, resendCode } from "../model/passwordless";
import { useCountdown } from "../model/use-countdown";
import type { SentTo } from "./email-form";
import { ProblemMessage } from "./problem-message";

const CODE_LENGTH = 6;
const SLOTS = [0, 1, 2, 3, 4, 5] as const;

/** Код из письма: шесть цифр, отправка сама на шестой; новый код — не раньше, чем разрешит сервер. */
export function CodeForm({
  sent,
  onArrival,
  onBack,
}: {
  sent: SentTo;
  onArrival: (outcome: Outcome<Arrival>) => void;
  onBack: () => void;
}) {
  const t = useTranslations("identity");
  const format = useFormatter();
  const [code, setCode] = useState("");
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [resent, setResent] = useState(false);
  const [pending, startTransition] = useTransition();
  const { remaining, restart } = useCountdown(sent.resendAfterSeconds);

  const confirm = (value: string) => {
    startTransition(async () => {
      const outcome = await confirmCode(sent.challenge, value);
      if (outcome.kind === "refused") {
        setRefusal(outcome);
        setCode("");
        return;
      }
      onArrival(outcome);
    });
  };

  const resend = () => {
    startTransition(async () => {
      const outcome = await resendCode(sent.challenge);
      setResent(outcome.kind === "done");
      setRefusal(outcome.kind === "done" ? null : outcome);
      if (outcome.kind === "done") restart(outcome.value.resendAfterSeconds);
      else if (outcome.retryAfterSeconds !== null) restart(outcome.retryAfterSeconds);
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
      {/* Код — цифры слева направо в любом языке. */}
      <div dir="ltr" className="flex justify-center">
        <InputOTP
          aria-label={t("code.label")}
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
              <InputOTPSlot key={slot} index={slot} className="size-12 text-lg" />
            ))}
          </InputOTPGroup>
        </InputOTP>
      </div>
      {refusal === null ? null : <ProblemMessage refusal={refusal} />}
      {resent && refusal === null ? (
        <p aria-live="polite" className="text-muted-foreground text-sm">
          {t("code.resent")}
        </p>
      ) : null}
      <Button type="submit" size="lg" className="h-11" disabled={pending || code.length !== CODE_LENGTH}>
        {pending ? <Spinner data-icon="inline-start" /> : null}
        {t("code.submit")}
      </Button>
      <div className="flex flex-col items-center gap-1 text-sm">
        <Button type="button" variant="link" className="px-0" onClick={onBack}>
          {t("code.back")}
        </Button>
        {remaining > 0 ? (
          <span className="text-muted-foreground">
            {t("code.resendIn", { time: format.number(remaining, { style: "unit", unit: "second" }) })}
          </span>
        ) : (
          <Button type="button" variant="link" className="px-0" disabled={pending} onClick={resend}>
            {t("code.resend")}
          </Button>
        )}
      </div>
    </form>
  );
}
