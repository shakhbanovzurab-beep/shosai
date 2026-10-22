"use client";

import { useState } from "react";

import { Plus } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";

import {
  BOARD_STICKERS_MAX,
  type BoardSticker,
  type CustomSticker,
  isCustomSticker,
  isTimeSticker,
} from "../../domain/stickers-contract";
import { useBoardStickers } from "../../model/board-hooks";
import { useBoardCommands, useEditable, useManagedByJira } from "../board-store";
import { useFieldName } from "../field-name";
import { dropFieldFilter } from "../filters/filter-address";
import { FieldAction, FieldActions, FieldCard } from "./field-card";
import { FieldDialog, type FieldRequest } from "./field-dialog";
import { FieldHint } from "./field-hint";
import { OtherBoardsPicker } from "./other-boards-picker";
import { StopwatchSetup } from "./stopwatch-setup";

/** Действия поля: своё правится и снимается с доски, у секундомера — автоматизации. */
function ActionsFor({ sticker, onEdit }: { sticker: BoardSticker; onEdit: (sticker: CustomSticker) => void }) {
  const t = useTranslations("kanbanFields");
  const { fields } = useBoardCommands();
  if (sticker.id === "stopwatch") return <StopwatchSetup automations={sticker.automations} />;
  if (!isCustomSticker(sticker)) return null;
  return (
    <FieldActions>
      <FieldAction onClick={() => onEdit(sticker)}>{t("edit")}</FieldAction>
      <FieldAction onClick={() => void fields.takeOff(sticker)}>{t("takeOff")}</FieldAction>
    </FieldActions>
  );
}

/** Лист «Поля»: что показывают карточки доски; свои поля — новые, с других досок, правка и снятие. */
export function FieldsBody() {
  const t = useTranslations("kanbanFields");
  const { fields } = useBoardCommands();
  const stickers = useBoardStickers();
  const fieldName = useFieldName();
  const editable = useEditable();
  const jira = useManagedByJira();
  const [request, setRequest] = useState<FieldRequest | null>(null);
  const custom = stickers.filter(isCustomSticker);
  const full = custom.length >= BOARD_STICKERS_MAX;
  const canAdd = editable && !jira && !full;
  return (
    <div className="flex flex-col gap-4">
      {jira ? (
        <p className="text-muted-foreground text-sm">{t("jiraOnly")}</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          <Button size="sm" disabled={!canAdd} onClick={() => setRequest({ mode: "new" })}>
            <Plus data-icon="inline-start" />
            {t("new")}
          </Button>
          <OtherBoardsPicker disabled={!canAdd} onPick={(id) => void fields.place({ sticker_id: id })} />
        </div>
      )}
      {full ? <p className="text-muted-foreground text-sm">{t("boardFull", { max: BOARD_STICKERS_MAX })}</p> : null}
      <div className="grid gap-3 sm:grid-cols-2">
        {stickers.map((sticker) => (
          <FieldCard
            key={sticker.id}
            sticker={sticker}
            editable={editable}
            onVisible={(visible) => {
              // Скрытое поле теряет и чип фильтра, и сам фильтр в адресе.
              if (!visible) dropFieldFilter(sticker.id);
              void fields.setVisible(sticker.id, visible);
            }}
            hint={isTimeSticker(sticker.id) ? <FieldHint field={sticker.id} name={fieldName(sticker)} /> : null}
          >
            {editable ? (
              <ActionsFor sticker={sticker} onEdit={(owned) => setRequest({ mode: "edit", sticker: owned })} />
            ) : null}
          </FieldCard>
        ))}
      </div>
      {custom.length === 0 && !jira ? <p className="text-muted-foreground text-sm">{t("onlySystem")}</p> : null}
      <FieldDialog request={request} onClose={() => setRequest(null)} />
    </div>
  );
}
