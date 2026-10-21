"use client";

import { useId, useState } from "react";

import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { FieldLabel } from "@/components/ui/field-text";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

import { CUSTOM_KINDS, type CustomKind, type CustomSticker, type OwnedSticker } from "../../domain/stickers-contract";
import { useBoardCommands } from "../board-store";
import { DeleteFieldDialog } from "./delete-field-dialog";

/** Вид нового поля: набор состояний, число, текст. */
export function KindPicker({ kind, onChange }: { kind: CustomKind; onChange: (kind: CustomKind) => void }) {
  const t = useTranslations("kanbanFields");
  const labelId = useId();
  return (
    <Field>
      <FieldLabel id={labelId}>{t("dialog.kind")}</FieldLabel>
      <ToggleGroup
        type="single"
        variant="outline"
        aria-labelledby={labelId}
        value={kind}
        onValueChange={(next) => (next ? onChange(next as CustomKind) : undefined)}
      >
        {CUSTOM_KINDS.map((item) => (
          <ToggleGroupItem key={item} value={item}>
            {t(`kinds.${item}`)}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </Field>
  );
}

/** «Удалить поле» в правке: спрашивает, называя доски и число задач, и удаляет. */
export function DeleteFieldButton({
  sticker,
  owned,
  onDeleted,
}: {
  sticker: CustomSticker;
  owned: OwnedSticker | undefined;
  onDeleted: () => void;
}) {
  const t = useTranslations("kanbanFields");
  const { fields } = useBoardCommands();
  const [asking, setAsking] = useState(false);
  return (
    <>
      <Button type="button" variant="ghost" className="text-destructive" onClick={() => setAsking(true)}>
        {t("dialog.delete")}
      </Button>
      <DeleteFieldDialog
        sticker={sticker}
        owned={owned}
        open={asking}
        onOpenChange={setAsking}
        onConfirm={() => void fields.remove(sticker).then((done) => (done ? onDeleted() : undefined))}
      />
    </>
  );
}
