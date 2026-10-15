"use client";

import { useTranslations } from "use-intl";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/** Адрес аккаунта, набранный заново: без него удаление не начнётся. */
export function ConfirmEmailField({
  email,
  value,
  mismatch,
  onChange,
}: {
  email: string;
  value: string;
  mismatch: boolean;
  onChange: (value: string) => void;
}) {
  const t = useTranslations("settings");
  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor="delete-confirm-email">
        {t.rich("deleteAccount.confirmLabel", {
          email,
          address: (chunks) => (
            <span dir="auto" className="font-mono">
              {chunks}
            </span>
          ),
        })}
      </Label>
      <Input
        id="delete-confirm-email"
        type="email"
        dir="auto"
        autoComplete="off"
        aria-invalid={mismatch}
        value={value}
        onChange={(event) => onChange(event.currentTarget.value)}
      />
      {mismatch ? <p className="text-destructive text-sm">{t("deleteAccount.mismatch")}</p> : null}
    </div>
  );
}
