"use client";

import { useId } from "react";

/**
 * Имя кнопки поля — подпись строки и сама кнопка с её значением: читается «Исполнитель, Майя Чен», а не одна
 * подпись без значения.
 */
export function useValueLabel(labelId: string) {
  const id = useId();
  return { id, "aria-labelledby": `${labelId} ${id}` };
}
