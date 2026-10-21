"use client";

import { useTranslations } from "use-intl";

import { type BoardSticker, isCustomSticker } from "../domain/stickers-contract";

/** Имя поля: у системного — на языке человека, у своего — как его назвали. */
export function useFieldName() {
  const t = useTranslations("kanbanPanel");
  return (sticker: BoardSticker) => (isCustomSticker(sticker) ? sticker.name : t(`fields.${sticker.kind}`));
}
