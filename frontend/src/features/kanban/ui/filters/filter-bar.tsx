"use client";

import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";

import { type BoardSticker, isCustomSticker } from "../../domain/stickers-contract";
import { useBoardStickers } from "../../model/board-hooks";
import { useFieldName } from "../field-name";
import { NumberChip, StatesChip, TextChip } from "./field-chips";
import { clearFilter } from "./filter-address";
import { AssigneeChip, DueChip, PriorityChip, RepeatChip } from "./system-chips";
import { StopwatchChip, TimerChip, TrackingChip } from "./time-chips";
import { useShownCount } from "./use-visible-cards";

/** Чип своего вида для каждого поля, видимого на карточках. */
function ChipFor({ sticker }: { sticker: BoardSticker }) {
  const field = useFieldName()(sticker);
  if (isCustomSticker(sticker)) {
    if (sticker.kind === "states") return <StatesChip sticker={sticker} />;
    return sticker.kind === "number" ? <NumberChip sticker={sticker} /> : <TextChip sticker={sticker} />;
  }
  if (sticker.kind === "stopwatch") return <StopwatchChip field={field} />;
  if (sticker.kind === "timer") return <TimerChip field={field} />;
  if (sticker.kind === "time_tracking") return <TrackingChip field={field} />;
  if (sticker.kind === "assignee") return <AssigneeChip field={field} />;
  if (sticker.kind === "due") return <DueChip field={field} />;
  return sticker.kind === "priority" ? <PriorityChip field={field} /> : <RepeatChip field={field} />;
}

/**
 * Фильтры доски в строке панели, сразу за выбором вида: по чипу на видимое поле; вместе они сужают доску,
 * «Сбросить фильтры» возвращает всё. Не помещаются — листаются вбок; сколько карточек видно, говорится вежливо.
 */
export function FilterBar() {
  const t = useTranslations("kanbanFilters");
  const stickers = useBoardStickers();
  const { shown, total, filtering } = useShownCount();
  return (
    <search
      aria-label={t("label")}
      // Поля вокруг — чтобы рамка фокуса чипов не обрезалась прокруткой; затухающий край говорит, что дальше ещё
      // фильтры, а колесо мыши листает строку вбок.
      className="scroll-fade-x scrollbar-none -m-1 flex min-w-0 flex-1 items-center gap-2 overflow-x-auto p-1"
      onWheel={(event) => {
        const row = event.currentTarget;
        if (event.deltaX === 0 && row.scrollWidth > row.clientWidth) row.scrollLeft += event.deltaY;
      }}
    >
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
