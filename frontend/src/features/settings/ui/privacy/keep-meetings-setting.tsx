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
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { keepMeetings, retryKeepsMeetings, useKeepsMeetings } from "@/features/notes/model/meeting-settings";
import { apiErrorDescription } from "@/lib/api/error-description";

import { SettingsGroup, SettingsRow } from "../settings-row";

const SWITCH_ID = "setting-dont-keep-meetings";

/**
 * «Не сохранять мои встречи» (MT-D6, настройка «Заметок»). Включить — значит потерять всё, что останется от
 * следующих встреч, поэтому сначала объясняем это и ждём подтверждения; выключается сразу.
 */
export function KeepMeetingsSetting() {
  const t = useTranslations("settingsPrivacy");
  const common = useTranslations("common");
  const words = useTranslations("settings");
  const state = useKeepsMeetings();
  const [confirming, setConfirming] = useState(false);

  const save = (keep: boolean) =>
    keepMeetings(keep).catch((error: unknown) =>
      toast.error(words("saveFailed"), { description: apiErrorDescription(error) }),
    );

  // Заглушка размером с переключатель: ряд не прыгает, когда настройка загрузилась.
  let control = <Skeleton className="h-[18.4px] w-8 rounded-full" />;
  if (state.status === "error")
    control = (
      <Button variant="outline" size="xs" onClick={() => void retryKeepsMeetings()}>
        {common("actions.retry")}
      </Button>
    );
  else if (state.status === "ready")
    control = (
      <Switch
        id={SWITCH_ID}
        checked={!state.data}
        onCheckedChange={(dontKeep) => (dontKeep ? setConfirming(true) : void save(true))}
      />
    );

  return (
    <SettingsGroup title={t("meetings")}>
      <SettingsRow title={t("dontKeepMeetings")} description={t("dontKeepMeetingsHint")} htmlFor={SWITCH_ID}>
        {control}
        <AlertDialog open={confirming} onOpenChange={setConfirming}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{t("dontKeepMeetingsConfirmTitle")}</AlertDialogTitle>
              <AlertDialogDescription>{t("dontKeepMeetingsConfirm")}</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{common("actions.cancel")}</AlertDialogCancel>
              <AlertDialogAction variant="destructive" onClick={() => void save(false)}>
                {t("dontKeepMeetingsConfirmAction")}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </SettingsRow>
    </SettingsGroup>
  );
}
