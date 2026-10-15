"use client";

import { useState } from "react";

import { toast } from "sonner";
import { useTranslations } from "use-intl";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Switch } from "@/components/ui/switch";
import type { Me } from "@/features/identity/domain/session";
import { type ConsentsPatch, saveConsents } from "@/features/identity/model/profile";
import { apiErrorDescription } from "@/lib/api/error-description";

import { SettingsRow } from "../settings-row";

type ConsentKind = keyof ConsentsPatch & keyof Me["consents"];

/**
 * Согласие, которое человек меняет сам; сохраняется сразу. Отзыв трансграничной передачи сначала объясняет, что
 * перестанет работать, и только после подтверждения уходит на сервер.
 */
export function ConsentSwitch({
  me,
  kind,
  title,
  description,
}: {
  me: Me;
  kind: ConsentKind;
  title: string;
  description: string;
}) {
  const t = useTranslations("settingsPrivacy");
  const common = useTranslations("common");
  const words = useTranslations("settings");
  const [warning, setWarning] = useState(false);
  const id = `consent-${kind}`;

  const save = (value: boolean, confirmed = false) =>
    saveConsents({ [kind]: value }, confirmed).catch((error: unknown) =>
      toast.error(words("saveFailed"), { description: apiErrorDescription(error) }),
    );

  return (
    <SettingsRow title={title} description={description} htmlFor={id}>
      <Switch
        id={id}
        checked={me.consents[kind]}
        onCheckedChange={(value) => {
          if (kind === "cross_border" && !value) setWarning(true);
          else void save(value);
        }}
      />
      <AlertDialog open={warning} onOpenChange={setWarning}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("crossBorderWarningTitle")}</AlertDialogTitle>
            <AlertDialogDescription>{t("crossBorderWarning")}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{common("actions.cancel")}</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={() => void save(false, true)}>
              {t("crossBorderWithdraw")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </SettingsRow>
  );
}
