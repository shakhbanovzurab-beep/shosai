"use client";

import type { ReactNode, Ref } from "react";

import { useTranslations } from "use-intl";

import type { BoardSticker, SystemStickerId } from "../domain/stickers-contract";
import type { Card } from "../domain/tasks-contract";
import { useBoardStickers, useCard, useColumn } from "../model/board-hooks";
import { BoardActionsButton } from "./board-menu-triggers";
import {
  CardAssignee,
  CardChips,
  CardCover,
  CardFooter,
  CardHeader,
  CardOpenButton,
  CardRoot,
  type CardState,
} from "./card/card-face";
import { hasFooterFacts } from "./card/footer-facts";
import { JiraKey } from "./jira-key";
import { openTask } from "./panel/task-address";
import { WorkspaceTaskLink } from "./workspace-task-link";

/** Какие системные поля показаны на этой доске. */
function visibilityOf(stickers: BoardSticker[]): Record<SystemStickerId, boolean> {
  const shown = (id: SystemStickerId) => stickers.find((s) => s.id === id)?.visible ?? false;
  return {
    assignee: shown("assignee"),
    due: shown("due"),
    priority: shown("priority"),
    recurrence: shown("recurrence"),
    stopwatch: shown("stopwatch"),
    timer: shown("timer"),
    time_tracking: shown("time_tracking"),
  };
}

/** Тело карточки без действий: обложка, заголовок, где живёт задача, чипы и низ. */
function CardBody({
  card,
  state,
  title,
  actions,
}: {
  card: Card;
  state: CardState;
  title: ReactNode;
  actions?: ReactNode;
}) {
  const stickers = useBoardStickers();
  const visible = visibilityOf(stickers);
  const assignee = visible.assignee ? <CardAssignee card={card} /> : null;
  return (
    <>
      {card.cover ? <CardCover previewUrl={card.cover.preview_url} /> : null}
      <CardHeader title={title} state={state}>
        {actions}
      </CardHeader>
      {card.jira ? <JiraKey issue={card.jira} /> : null}
      {card.space ? <WorkspaceTaskLink space={card.space} /> : null}
      {/* Исполнитель — в конце нижней строки, а если внизу больше ничего нет, то в конце строки чипов. */}
      <CardChips card={card} stickers={stickers} visible={visible} trailing={hasFooterFacts(card) ? null : assignee} />
      <CardFooter card={card} trailing={hasFooterFacts(card) ? assignee : null} />
    </>
  );
}

/** Карточка на доске: лицо задачи и «⋮». В закрытой колонке — приглушённая. `handleRef` — ручка перетаскивания. */
export function TaskCard({
  taskId,
  columnId,
  handleRef,
}: {
  taskId: string;
  columnId: string;
  handleRef?: Ref<HTMLButtonElement>;
}) {
  const card = useCard(taskId);
  const state: CardState = useColumn(columnId)?.kind === "done" ? "done" : "open";
  const tc = useTranslations("common");
  if (!card) return null;
  return (
    <CardRoot state={state}>
      <CardBody
        card={card}
        state={state}
        title={
          <CardOpenButton onOpen={() => openTask(taskId)} handleRef={handleRef}>
            {card.title}
          </CardOpenButton>
        }
        actions={
          <BoardActionsButton
            target={{ kind: "task", taskId, columnId }}
            label={tc("actionsFor", { name: card.title })}
            className="relative z-10 -my-1 -me-1.5 shrink-0 text-muted-foreground"
          />
        }
      />
    </CardRoot>
  );
}

/** Превью под пальцем или курсором при перетаскивании: то же лицо, без действий, чуть приподнятое. */
export function DragPreview({ taskId, columnId }: { taskId: string; columnId: string }) {
  const card = useCard(taskId);
  const state: CardState = useColumn(columnId)?.kind === "done" ? "done" : "open";
  if (!card) return null;
  return (
    <CardRoot state={state} className="w-68 rotate-1 shadow-lg">
      <CardBody card={card} state={state} title={card.title} />
    </CardRoot>
  );
}
