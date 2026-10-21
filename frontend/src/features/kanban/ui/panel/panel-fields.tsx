"use client";

import { useId } from "react";

import { useTranslations } from "use-intl";

import type { CustomSticker, StickerValue } from "../../domain/stickers-contract";
import type { LeoField, TaskDetail } from "../../domain/tasks-contract";
import { useBoardStickers } from "../../model/board-hooks";
import { AssigneeField } from "./assignee-field";
import { DeadlineField } from "./deadline-field";
import { FieldRow } from "./field-row";
import { LeoSource } from "./leo-source";
import { PriorityField } from "./priority-field";
import { RepeatField } from "./repeat-field";
import { usePanelActions } from "./use-panel-actions";
import { ValueField } from "./value-fields";

type Props = { detail: TaskDetail; editable: boolean };

/** Метка «Заполнил Лео» у поля, пока человек его не поменял. */
function LeoFor({ detail, field }: { detail: TaskDetail; field: LeoField }) {
  return detail.leo_fields.includes(field) ? <LeoSource source={detail.source} /> : null;
}

function CustomRow({
  sticker,
  value,
  editable,
  onChange,
}: {
  sticker: CustomSticker;
  value: StickerValue | undefined;
  editable: boolean;
  onChange: (value: StickerValue | null) => void;
}) {
  const labelId = useId();
  return (
    <FieldRow label={sticker.name} labelId={labelId}>
      <ValueField sticker={sticker} value={value} labelId={labelId} disabled={!editable} onChange={onChange} />
    </FieldRow>
  );
}

/** Поля задачи: системные, свои поля доски (и скрытые на карточках тоже), затем поля с других досок. */
export function PanelFields({ detail, editable }: Props) {
  const t = useTranslations("kanbanPanel");
  const actions = usePanelActions(detail.id);
  const stickers = useBoardStickers();
  const ids = { assignee: useId(), due: useId(), priority: useId(), repeat: useId() };
  return (
    <div className="flex flex-col gap-3">
      <dl className="flex flex-col gap-3">
        <FieldRow label={t("fields.assignee")} labelId={ids.assignee}>
          <AssigneeField
            assignee={detail.assignee}
            space={detail.space}
            labelId={ids.assignee}
            disabled={!editable}
            onChange={(name) => void actions.patch({ assignee_name: name })}
          />
          <LeoFor detail={detail} field="assignee" />
        </FieldRow>
        <FieldRow label={t("fields.due")} labelId={ids.due}>
          <DeadlineField
            dates={{ starts_on: detail.starts_on, due_on: detail.due_on }}
            labelId={ids.due}
            disabled={!editable}
            modes={["day", "range"]}
            onChange={(patch) => void actions.patch(patch)}
          />
          <LeoFor detail={detail} field="due" />
        </FieldRow>
        <FieldRow label={t("fields.priority")} labelId={ids.priority}>
          <PriorityField
            value={detail.priority}
            labelId={ids.priority}
            disabled={!editable}
            onChange={(priority) => void actions.patch({ priority })}
          />
          <LeoFor detail={detail} field="priority" />
        </FieldRow>
        <FieldRow label={t("fields.recurrence")} labelId={ids.repeat}>
          <RepeatField
            value={detail.recurrence}
            dueOn={detail.due_on}
            labelId={ids.repeat}
            disabled={!editable}
            onChange={(recurrence) => void actions.patch({ recurrence })}
          />
        </FieldRow>
        {stickers.map((sticker) =>
          sticker.kind === "states" || sticker.kind === "number" || sticker.kind === "text" ? (
            <CustomRow
              key={sticker.id}
              sticker={sticker}
              value={detail.values[sticker.id]}
              editable={editable}
              onChange={(value) => void actions.setValue(sticker.id, value)}
            />
          ) : null,
        )}
      </dl>
      {detail.other_values.length > 0 ? (
        <section aria-label={t("fields.other")} className="flex flex-col gap-3">
          <h3 className="font-medium text-muted-foreground text-xs">{t("fields.other")}</h3>
          <dl className="flex flex-col gap-3">
            {detail.other_values.map(({ sticker, value }) => (
              <CustomRow
                key={sticker.id}
                sticker={sticker}
                value={value}
                editable={editable}
                onChange={(next) => void actions.setValue(sticker.id, next)}
              />
            ))}
          </dl>
        </section>
      ) : null}
    </div>
  );
}

/** Поля задачи Jira — только те, что знает Jira: исполнитель (меняют в Jira), срок одним днём, приоритет. */
export function JiraFields({ detail, editable }: Props) {
  const t = useTranslations("kanbanPanel");
  const tk = useTranslations("kanban");
  const actions = usePanelActions(detail.id);
  const ids = { assignee: useId(), due: useId(), priority: useId() };
  return (
    <dl className="flex flex-col gap-3">
      <FieldRow label={t("fields.assignee")} labelId={ids.assignee}>
        <span dir="auto" className="text-sm">
          {detail.assignee?.name ?? tk("card.unassigned")}
        </span>
      </FieldRow>
      <FieldRow label={t("fields.due")} labelId={ids.due}>
        <DeadlineField
          dates={{ starts_on: null, due_on: detail.due_on }}
          labelId={ids.due}
          disabled={!editable}
          modes={["day"]}
          onChange={(patch) => void actions.patch({ due_on: patch.due_on })}
        />
      </FieldRow>
      <FieldRow label={t("fields.priority")} labelId={ids.priority}>
        <PriorityField
          value={detail.priority}
          labelId={ids.priority}
          disabled={!editable}
          onChange={(priority) => void actions.patch({ priority })}
        />
      </FieldRow>
    </dl>
  );
}
