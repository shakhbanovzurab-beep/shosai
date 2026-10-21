"use client";

import { Sparkles } from "lucide-react";
import { useTranslations } from "use-intl";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

/**
 * Метка «это заполнил Лео» внутри поля карточки (KG-D10): значок с подсказкой для мыши и словами для чтения с
 * экрана. Источник — встреча и цитата — в панели задачи; метка уходит, когда человек меняет поле.
 */
export function LeoMark() {
  const t = useTranslations("kanban");
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="relative z-10 inline-flex shrink-0 text-violet-600 dark:text-violet-400" data-leo-mark>
          <Sparkles className="size-3" aria-hidden="true" />
          <span className="sr-only">{t("card.leoFilled")}</span>
        </span>
      </TooltipTrigger>
      <TooltipContent>{t("card.leoFilled")}</TooltipContent>
    </Tooltip>
  );
}
