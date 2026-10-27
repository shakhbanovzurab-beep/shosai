"use client";

import { Lightbulb } from "lucide-react";
import { useTranslations } from "use-intl";

import { InputGroupButton } from "@/components/ui/input-group";

type LeoThinkLongerProps = { readonly on: boolean; readonly onToggle: () => void };

/**
 * «Думать дольше», как в ChatGPT: пока включено, каждый вопрос Leo обдумывает в полную силу — медленнее и дороже.
 * Включённое видно подписью рядом со скрепкой и остаётся, пока его не выключат.
 */
export function LeoThinkLonger({ on, onToggle }: LeoThinkLongerProps) {
  const t = useTranslations("leo");
  return (
    <InputGroupButton
      type="button"
      size={on ? "sm" : "icon-sm"}
      variant={on ? "secondary" : "ghost"}
      className="rounded-full"
      aria-pressed={on}
      aria-label={t("composer.thinkLonger")}
      title={t("composer.thinkLongerHint")}
      onClick={onToggle}
    >
      <Lightbulb />
      {on ? <span>{t("composer.thinkLonger")}</span> : null}
    </InputGroupButton>
  );
}
