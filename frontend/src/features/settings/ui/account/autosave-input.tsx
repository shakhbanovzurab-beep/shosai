"use client";

import { useState } from "react";

import { useTranslations } from "next-intl";

import { Input } from "@/components/ui/input";
import { useAutosave } from "@/hooks/use-autosave";

import { NAME_MAX, type SettingsPatch } from "../../domain/settings-contract";
import { saveSettings } from "../../model/account-actions";

type TextField = "full_name" | "display_name";

/** A text setting that saves itself a moment after you stop typing, and on blur. */
export function AutosaveInput({ id, field, initialValue }: { id: string; field: TextField; initialValue: string }) {
  const t = useTranslations("settings");
  const [value, setValue] = useState(initialValue);
  const autosave = useAutosave((next) => saveSettings({ [field]: next } as SettingsPatch, t));

  return (
    <div className="flex flex-col gap-1">
      <Input
        id={id}
        dir="auto"
        value={value}
        maxLength={NAME_MAX}
        onChange={(event) => {
          setValue(event.currentTarget.value);
          if (event.currentTarget.value.trim() || field !== "full_name") autosave.schedule(event.currentTarget.value);
        }}
        onBlur={autosave.flush}
        className="w-full sm:w-64"
      />
      <span className="h-4 text-muted-foreground text-xs" aria-live="polite">
        {autosave.status === "saving" || autosave.status === "pending" ? t("saving") : null}
        {autosave.status === "error" ? t("saveFailed") : null}
      </span>
    </div>
  );
}
