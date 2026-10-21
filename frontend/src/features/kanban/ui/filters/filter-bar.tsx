"use client";

import { Search } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group";

import { type BoardSticker, isCustomSticker } from "../../domain/stickers-contract";
import { useBoardStickers } from "../../model/board-hooks";
import { useFieldName } from "../field-name";
import { NumberChip, StatesChip, TextChip } from "./field-chips";
import { clearFilter, setFilter, useFilterAddress } from "./filter-address";
import { AssigneeChip, DueChip, PriorityChip, RepeatChip } from "./system-chips";
import { useShownCount } from "./use-visible-cards";

/** Чип своего вида для каждого поля, видимого на карточках. */
function ChipFor({ sticker }: { sticker: BoardSticker }) {
  const field = useFieldName()(sticker);
  if (isCustomSticker(sticker)) {
    if (sticker.kind === "states") return <StatesChip sticker={sticker} />;
    return sticker.kind === "number" ? <NumberChip sticker={sticker} /> : <TextChip sticker={sticker} />;
  }
  if (sticker.kind === "assignee") return <AssigneeChip field={field} />;
  if (sticker.kind === "due") return <DueChip field={field} />;
  return sticker.kind === "priority" ? <PriorityChip field={field} /> : <RepeatChip field={field} />;
}

/**
 * Строка фильтра под панелью доски: поиск и по чипу на видимое поле; всё вместе сужает доску, «Сбросить фильтры»
 * возвращает всё. На телефоне строка листается вбок; сколько карточек видно, говорится вежливо.
 */
export function FilterBar() {
  const t = useTranslations("kanbanFilters");
  const stickers = useBoardStickers();
  const { q } = useFilterAddress();
  const { shown, total, filtering } = useShownCount();
  return (
    <search
      aria-label={t("label")}
      className="scrollbar-thin flex shrink-0 items-center gap-2 overflow-x-auto border-b px-4 py-2 lg:px-6"
    >
      <InputGroup className="w-44 shrink-0 sm:w-56">
        <InputGroupAddon>
          <Search />
        </InputGroupAddon>
        <InputGroupInput
          type="search"
          value={q}
          dir="auto"
          aria-label={t("search")}
          placeholder={t("searchPlaceholder")}
          onChange={(event) => {
            const next = event.currentTarget.value;
            setFilter((current) => ({ ...current, q: next }));
          }}
        />
      </InputGroup>
      {stickers.map((sticker) => (sticker.visible ? <ChipFor key={sticker.id} sticker={sticker} /> : null))}
      {filtering ? (
        <Button variant="ghost" size="sm" className="shrink-0" onClick={clearFilter}>
          {t("clear")}
        </Button>
      ) : null}
      <p className="sr-only" aria-live="polite">
        {filtering ? t("shown", { shown, total }) : ""}
      </p>
    </search>
  );
}
