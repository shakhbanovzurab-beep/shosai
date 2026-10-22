"use client";

import { useTranslations } from "use-intl";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

import { LeoOrb } from "../leo-orb";

/**
 * Метка «это заполнил Лео» внутри поля карточки (KG-D10): кольцо Leo с подсказкой для мыши и словами для чтения с
 * экрана. Источник — встреча и цитата — в панели задачи; метка уходит, когда человек меняет поле.
 */
export function LeoMark() {
  const t = useTranslations("kanban");
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="relative z-10 inline-flex shrink-0" data-leo-mark>
          <LeoOrb className="size-3.5" />
          <span className="sr-only">{t("card.leoFilled")}</span>
        </span>
      </TooltipTrigger>
      <TooltipContent>{t("card.leoFilled")}</TooltipContent>
    </Tooltip>
  );
}
