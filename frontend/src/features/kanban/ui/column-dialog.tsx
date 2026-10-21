"use client";

import { useActionState, useState } from "react";

import { cn } from "cn";
import { Ban } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, FieldGroup, FieldLegend, FieldSet } from "@/components/ui/field";
import { FieldLabel } from "@/components/ui/field-text";
import { Input } from "@/components/ui/input";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

import { BOARD_NAME_MAX, COLUMN_KINDS, type ColumnKind } from "../domain/board";
import { COLORS, type Color } from "../domain/stickers-contract";
import type { ColumnLifecycle } from "../model/column-lifecycle";
import { SWATCHES } from "./palette";

const NO_COLOUR = "none";

/** Выбор цвета: образцы палитры и «без цвета», с названиями для чтения с экрана. */
export function ColourChoice({ value, onChange }: { value: Color | null; onChange: (color: Color | null) => void }) {
  const t = useTranslations("kanban");
  return (
    <ToggleGroup
      type="single"
      variant="outline"
      value={value ?? NO_COLOUR}
      onValueChange={(next) => (next ? onChange(next === NO_COLOUR ? null : (next as Color)) : undefined)}
      className="flex-wrap"
    >
      <ToggleGroupItem value={NO_COLOUR} aria-label={t("colors.none")}>
        <Ban />
      </ToggleGroupItem>
      {COLORS.map((color) => (
        <ToggleGroupItem key={color} value={color} aria-label={t(`colors.${color}`)}>
          <span className={cn("size-3 rounded-full", SWATCHES[color].dot)} aria-hidden="true" />
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}

/** Форма монтируется заново при каждом открытии, поэтому новая колонка начинается с умолчаний. */
function NewColumnForm({
  position,
  lifecycle,
  onDone,
}: {
  position: number;
  lifecycle: ColumnLifecycle;
  onDone: () => void;
}) {
  const t = useTranslations("kanban");
  const tc = useTranslations("common");
  const [kind, setKind] = useState<ColumnKind>("todo");
  const [color, setColor] = useState<Color | null>(null);
  const [, submit, pending] = useActionState(async (_: null, form: FormData) => {
    const title = String(form.get("title") ?? "").trim();
    if (!title) return null;
    if (await lifecycle.addColumn({ title, kind, position, color })) onDone();
    return null;
  }, null);

  return (
    <form action={submit} className="flex flex-col gap-4">
      <DialogHeader>
        <DialogTitle>{t("newColumn.title")}</DialogTitle>
      </DialogHeader>
      <FieldGroup>
        <Field>
          <FieldLabel htmlFor="column-title">{t("newColumn.name")}</FieldLabel>
          <Input id="column-title" name="title" required maxLength={BOARD_NAME_MAX} autoComplete="off" />
        </Field>
        <FieldSet>
          <FieldLegend variant="label">{t("newColumn.kind")}</FieldLegend>
          <ToggleGroup
            type="single"
            variant="outline"
            value={kind}
            onValueChange={(next) => (next ? setKind(next as ColumnKind) : undefined)}
          >
            {COLUMN_KINDS.map((value) => (
              <ToggleGroupItem key={value} value={value}>
                {t(`kinds.${value}`)}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </FieldSet>
        <FieldSet>
          <FieldLegend variant="label">{t("newColumn.colour")}</FieldLegend>
          <ColourChoice value={color} onChange={setColor} />
        </FieldSet>
      </FieldGroup>
      <DialogFooter>
        <DialogClose asChild>
          <Button type="button" variant="outline">
            {tc("actions.cancel")}
          </Button>
        </DialogClose>
        <Button type="submit" disabled={pending}>
          {t("newColumn.create")}
        </Button>
      </DialogFooter>
    </form>
  );
}

/** Новая колонка на месте `position` (null — диалог закрыт). */
export function NewColumnDialog({
  position,
  lifecycle,
  onClose,
}: {
  position: number | null;
  lifecycle: ColumnLifecycle;
  onClose: () => void;
}) {
  return (
    <Dialog open={position !== null} onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="sm:max-w-md">
        {position === null ? null : <NewColumnForm position={position} lifecycle={lifecycle} onDone={onClose} />}
      </DialogContent>
    </Dialog>
  );
}
