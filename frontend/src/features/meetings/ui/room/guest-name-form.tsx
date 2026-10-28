import { useId } from "react";

import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Field, FieldGroup } from "@/components/ui/field";
import { FieldDescription, FieldError, FieldLabel } from "@/components/ui/field-text";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";

import { GUEST_NAME_MAX, guestName, type JoinProblem } from "../../domain/join";

type GuestNameFormProps = {
  value: string;
  onChange: (value: string) => void;
  problem: JoinProblem | null;
  pending: boolean;
  onSubmit: () => void;
};

/** Имя гостя: так его увидят участники; без аккаунта — только на эту встречу. */
export function GuestNameForm({ value, onChange, problem, pending, onSubmit }: GuestNameFormProps) {
  const t = useTranslations("meetingRoom");
  const id = useId();
  const valid = guestName(value) !== null;
  return (
    <form
      aria-labelledby="join-title"
      className="flex flex-col gap-5"
      onSubmit={(event) => {
        event.preventDefault();
        if (valid) onSubmit();
      }}
    >
      <h1 id="join-title" className="font-semibold text-2xl tracking-tight">
        {t("join.nameTitle")}
      </h1>
      <FieldGroup>
        <Field data-invalid={problem !== null || undefined}>
          <FieldLabel htmlFor={id}>{t("join.nameLabel")}</FieldLabel>
          <Input
            id={id}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            maxLength={GUEST_NAME_MAX}
            autoComplete="name"
            dir="auto"
            aria-invalid={problem !== null || undefined}
            required
          />
          <FieldDescription>{t("join.nameHint")}</FieldDescription>
          {problem ? <FieldError>{t(`problems.${problem}.title`)}</FieldError> : null}
        </Field>
      </FieldGroup>
      <Button type="submit" size="lg" className="self-start" disabled={!valid || pending}>
        {pending ? <Spinner data-icon="inline-start" /> : null}
        {t("join.continue")}
      </Button>
    </form>
  );
}
