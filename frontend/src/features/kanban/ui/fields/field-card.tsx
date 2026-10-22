"use client";

import { type ComponentProps, createContext, type ReactNode, use, useId } from "react";

import {
  CalendarDays,
  CircleDot,
  Clock,
  Flag,
  Hash,
  Hourglass,
  type LucideIcon,
  Repeat,
  Timer,
  Type,
  UserRound,
} from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

import { type BoardSticker, isCustomSticker, type StickerKind } from "../../domain/stickers-contract";
import { useFieldName } from "../field-name";

const ICONS: Record<StickerKind, LucideIcon> = {
  assignee: UserRound,
  due: CalendarDays,
  priority: Flag,
  recurrence: Repeat,
  stopwatch: Timer,
  timer: Hourglass,
  time_tracking: Clock,
  states: CircleDot,
  number: Hash,
  text: Type,
};

const FieldNameId = createContext<string | undefined>(undefined);

/** Строка действий поля под переключателем. */
export function FieldActions({ children }: { children: ReactNode }) {
  return <div className="-mx-2 -mb-1.5 flex flex-wrap items-center gap-1">{children}</div>;
}

/** Действие поля: для чтения с экрана описано именем поля («Изменить» — какое). */
export function FieldAction(props: ComponentProps<typeof Button>) {
  return <Button variant="ghost" size="sm" aria-describedby={use(FieldNameId)} {...props} />;
}

/**
 * Поле доски: значок, имя, вид, «Показывать на карточках». `hint` — пояснение рядом с именем, `children` — действия
 * под переключателем (правка своего поля, настройка секундомера).
 */
export function FieldCard({
  sticker,
  editable,
  onVisible,
  hint,
  children,
}: {
  sticker: BoardSticker;
  editable: boolean;
  onVisible: (visible: boolean) => void;
  hint?: ReactNode;
  children?: ReactNode;
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
          <span className="flex min-w-0 items-center gap-1">
            <span id={nameId} dir="auto" className="truncate font-medium text-sm">
              {name}
            </span>
            {hint}
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
      <FieldNameId value={nameId}>{children}</FieldNameId>
    </div>
  );
}
