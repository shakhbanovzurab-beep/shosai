"use client";

import * as React from "react";

import { cn } from "cn";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import { useTranslations } from "use-intl";

import type { LeoRating } from "../domain/types";
import { pressRating, useRating } from "../model/ratings";
import { MessageAction } from "./leo-message-actions";

/*
 * «Полезно» и «Не полезно» под законченным ответом (AG-D13): одно нажатие, повторное снимает оценку, без формы.
 * После оценки — короткая благодарность; если человек разрешил улучшать модели, она говорит, что разговор поможет.
 */

const HINT_MS = 4000;

export function RatingActions({ messageId, saved }: { readonly messageId: string; readonly saved: LeoRating | null }) {
  const t = useTranslations("leo");
  const { rating, busy } = useRating(messageId, saved);
  const [hint, setHint] = React.useState<"thanks" | "shared" | null>(null);

  React.useEffect(() => {
    if (hint === null) return;
    const timeout = setTimeout(() => setHint(null), HINT_MS);
    return () => clearTimeout(timeout);
  }, [hint]);

  const press = async (chosen: LeoRating) => {
    if (busy) return;
    const done = await pressRating(messageId, rating, chosen, t("rating.failed"));
    if (done === undefined) return;
    if (done.rating === null) setHint(null);
    else setHint(done.shared ? "shared" : "thanks");
  };

  return (
    <>
      <MessageAction
        aria-label={t("rating.useful")}
        title={t("rating.useful")}
        aria-pressed={rating === "useful"}
        className={rating === "useful" ? "text-foreground" : undefined}
        onClick={() => void press("useful")}
      >
        <ThumbsUp fill={rating === "useful" ? "currentColor" : "none"} />
      </MessageAction>
      <MessageAction
        aria-label={t("rating.notUseful")}
        title={t("rating.notUseful")}
        aria-pressed={rating === "not_useful"}
        className={rating === "not_useful" ? "text-foreground" : undefined}
        onClick={() => void press("not_useful")}
      >
        <ThumbsDown fill={rating === "not_useful" ? "currentColor" : "none"} />
      </MessageAction>
      {/* Подсказка — своей строкой под кнопками: в узкой панели она не сжимает ряд действий. */}
      <span
        role="status"
        className={cn("text-muted-foreground text-xs", hint !== null && "order-last basis-full ps-2 pt-0.5")}
      >
        {hint === null ? null : t(`rating.${hint}`)}
      </span>
    </>
  );
}
