"use client";

import { cn } from "cn";
import { Repeat } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import type { BoardSticker, CustomSticker, StickerValue } from "../../domain/stickers-contract";
import { SWATCHES } from "../palette";
import { Chip } from "./chip";

/** Значение своего поля как чип: состояние — цветом и названием, число — «Поле: 4», текст — сам текст. */
function FieldChip({ sticker, value }: { sticker: CustomSticker; value: StickerValue }) {
  const t = useTranslations("kanban");
  const format = useFormatter();
  if ("state_id" in value) {
    const state = sticker.states.find((s) => s.id === value.state_id);
    if (!state) return null;
    return (
      <Chip>
        <span className={cn("size-2 shrink-0 rounded-full", SWATCHES[state.color].dot)} aria-hidden="true" />
        <span dir="auto" className="truncate">
          {state.name}
        </span>
        <span className="sr-only">{t("card.fieldLabel", { field: sticker.name })}</span>
      </Chip>
    );
  }
  const shown =
    "number" in value ? t("card.fieldValue", { field: sticker.name, value: format.number(value.number) }) : value.text;
  return (
    <Chip>
      <span dir="auto" className="max-w-40 truncate">
        {shown}
      </span>
      {"text" in value ? <span className="sr-only">{t("card.fieldLabel", { field: sticker.name })}</span> : null}
    </Chip>
  );
}

const isCustom = (sticker: BoardSticker): sticker is CustomSticker & { visible: boolean } =>
  sticker.kind === "states" || sticker.kind === "number" || sticker.kind === "text";

/** Видимые свои поля доски, у которых у карточки есть значение, — в порядке доски. */
export function FieldChips({ stickers, values }: { stickers: BoardSticker[]; values: Record<string, StickerValue> }) {
  return (
    <>
      {stickers.map((sticker) => {
        const value = values[sticker.id];
        return value && sticker.visible && isCustom(sticker) ? (
          <FieldChip key={sticker.id} sticker={sticker} value={value} />
        ) : null;
      })}
    </>
  );
}

/** Отметка повторяющейся задачи. */
export function RepeatChip() {
  const t = useTranslations("kanban");
  return (
    <Chip>
      <Repeat className="size-3 shrink-0" aria-hidden="true" />
      <span className="sr-only">{t("card.repeats")}</span>
    </Chip>
  );
}
