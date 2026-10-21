"use client";

import { useId } from "react";

import { CalendarDays, CircleDot, Flag, Hash, type LucideIcon, Repeat, Type, UserRound } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

import {
  type BoardSticker,
  type CustomSticker,
  isCustomSticker,
  type StickerKind,
} from "../../domain/stickers-contract";
import { useFieldName } from "../field-name";

const ICONS: Record<StickerKind, LucideIcon> = {
  assignee: UserRound,
  due: CalendarDays,
  priority: Flag,
  recurrence: Repeat,
  states: CircleDot,
  number: Hash,
  text: Type,
};

/** Поле доски: значок, имя, вид, «Показывать на карточках»; своё ещё правится и снимается с доски. */
export function FieldCard({
  sticker,
  editable,
  onVisible,
  onEdit,
  onTakeOff,
}: {
  sticker: BoardSticker;
  editable: boolean;
  onVisible: (visible: boolean) => void;
  onEdit: (sticker: CustomSticker) => void;
  onTakeOff: (sticker: BoardSticker) => void;
}) {
  const t = useTranslations("kanbanFields");
  const name = useFieldName()(sticker);
  const switchId = useId();
  const nameId = useId();
  const Icon = ICONS[sticker.kind];
  const custom = isCustomSticker(sticker) ? sticker : null;
  return (
    <div className="flex flex-col gap-3 rounded-xl border bg-card p-3.5 text-card-foreground">
      <div className="flex items-start gap-2.5">
        <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <div className="flex min-w-0 flex-col">
          <span id={nameId} dir="auto" className="truncate font-medium text-sm">
            {name}
          </span>
          <span className="text-muted-foreground text-xs">{custom ? t(`kinds.${custom.kind}`) : t("system")}</span>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Switch
          id={switchId}
          checked={sticker.visible}
          disabled={!editable}
          aria-label={t("showOnCardsFor", { name })}
          onCheckedChange={onVisible}
        />
        <Label htmlFor={switchId} className="font-normal text-sm">
          {t("showOnCards")}
        </Label>
      </div>
      {custom && editable ? (
        <div className="-mx-2 -mb-1.5 flex flex-wrap gap-1">
          <Button variant="ghost" size="sm" aria-describedby={nameId} onClick={() => onEdit(custom)}>
            {t("edit")}
          </Button>
          <Button variant="ghost" size="sm" aria-describedby={nameId} onClick={() => onTakeOff(sticker)}>
            {t("takeOff")}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
