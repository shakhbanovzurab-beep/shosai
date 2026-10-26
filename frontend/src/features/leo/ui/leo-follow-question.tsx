"use client";

import * as React from "react";

import { useMessageScroller } from "@/components/ui/message-scroller";

/**
 * Новый вопрос человека всегда виден: разговор уходит к концу, даже если человек читал выше, и дальше
 * провожает ответ, пока его не прокрутят вверх. Сигнал — последний вопрос: подгрузка ранних сообщений
 * добавляет их сверху и его не меняет. Серверный id из `run.started` сменяет его ещё раз, у конца — без движения.
 */
export function LeoFollowQuestion({ lastQuestionId }: { readonly lastQuestionId: string | undefined }) {
  const { scrollToEnd } = useMessageScroller();
  const seen = React.useRef(lastQuestionId);

  React.useEffect(() => {
    if (lastQuestionId === seen.current) return;
    seen.current = lastQuestionId;
    if (lastQuestionId !== undefined) scrollToEnd({ behavior: "smooth" });
  }, [lastQuestionId, scrollToEnd]);

  return null;
}
