"use client";

import type { ReactNode, Ref } from "react";

import { cn } from "cn";
import { CircleCheck, MessageSquare, Paperclip } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import type { BoardSticker, SystemStickerId } from "../../domain/stickers-contract";
import type { Card } from "../../domain/tasks-contract";
import { PriorityBadge } from "../priority-badge";
import { OwnerAvatar } from "../task-owner";
import { ChatSourceLine } from "./chat-source";
import { DeadlineChip } from "./deadline-chip";
import { FieldChips, RepeatChip } from "./field-chips";
import { hasFooterFacts } from "./footer-facts";
import { LeoMark } from "./leo-mark";
import { TimeChips } from "./time-chips";

/*
 * Лицо карточки по частям (составной компонент): доска и превью перетаскивания собирают его из одних частей.
 * Тихо по умолчанию: видно только то, что задано.
 */

export type CardState = "open" | "done";

export function CardRoot({
  state,
  children,
  className,
}: {
  state: CardState;
  children: ReactNode;
  className?: string;
}) {
  return (
    <article
      data-state={state}
      className={cn(
        "relative flex flex-col gap-2.5 rounded-xl border bg-card p-3.5 text-card-foreground shadow-xs transition-colors has-[[data-card-open]:hover]:border-foreground/20",
        state === "done" && "bg-card/60 text-muted-foreground",
        className,
      )}
    >
      {children}
    </article>
  );
}

/**
 * Обложка в рамке 16:9: размер известен заранее, поэтому ничего не сдвигается, пока грузится превью. Картинка
 * декоративная (название задачи рядом), поэтому фон, а не <img>; карточку вне экрана браузер не рисует и превью
 * не грузит.
 */
export function CardCover({ previewUrl }: { previewUrl: string | null }) {
  return (
    <div
      aria-hidden="true"
      className="-mx-3.5 -mt-3.5 aspect-video rounded-t-xl border-b bg-center bg-cover bg-muted"
      style={previewUrl ? { backgroundImage: `url("${previewUrl.replace(/"/g, "%22")}")` } : undefined}
    />
  );
}

/** Заголовок в две строки и место для действий справа; `title` — текст или кнопка, открывающая карточку. */
export function CardHeader({ title, state, children }: { title: ReactNode; state: CardState; children?: ReactNode }) {
  return (
    <div className="flex items-start gap-2">
      {state === "done" ? <CircleCheck className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-hidden="true" /> : null}
      <h3 dir="auto" className="line-clamp-2 min-w-0 flex-1 break-words font-medium text-sm leading-5">
        {title}
      </h3>
      {children}
    </div>
  );
}

/**
 * Заголовок как кнопка «открыть»: растянут на всю карточку, поэтому открыть можно щелчком в любом месте. Это и
 * ручка перетаскивания: одна остановка Tab на карточку, Enter открывает, пробел поднимает. Кнопки и ссылки
 * карточки лежат поверх (`relative z-10`).
 */
export function CardOpenButton({
  onOpen,
  handleRef,
  children,
}: {
  onOpen: () => void;
  handleRef?: Ref<HTMLButtonElement>;
  children: ReactNode;
}) {
  return (
    <button
      ref={handleRef}
      type="button"
      data-card-open
      onClick={onOpen}
      // Рамка фокуса — внутри растянутого слоя: снаружи её обрезала бы content-visibility карточки.
      className="text-start outline-none after:absolute after:inset-0 after:rounded-xl after:content-[''] focus-visible:after:ring-2 focus-visible:after:ring-ring focus-visible:after:ring-inset"
    >
      {children}
    </button>
  );
}

type Visible = Record<SystemStickerId, boolean>;

/** Чипы: приоритет, срок, повтор, свои поля — каждый, только если задан и показан на доске; `trailing` — в конце. */
export function CardChips({
  card,
  stickers,
  visible,
  trailing,
}: {
  card: Card;
  stickers: BoardSticker[];
  visible: Visible;
  trailing?: ReactNode;
}) {
  const leo = new Set(card.leo_fields);
  const priority = visible.priority ? card.priority : null;
  const due = visible.due ? card.due_on : null;
  return (
    <div className="flex flex-wrap items-center gap-1.5 empty:hidden">
      {priority ? <PriorityBadge priority={priority}>{leo.has("priority") ? <LeoMark /> : null}</PriorityBadge> : null}
      {due ? (
        <DeadlineChip startsOn={card.starts_on} dueOn={due} done={card.status === "done"} byLeo={leo.has("due")} />
      ) : null}
      {visible.recurrence && card.recurring ? <RepeatChip /> : null}
      <TimeChips card={card} visible={visible} />
      <FieldChips stickers={stickers} values={card.values} />
      {trailing}
    </div>
  );
}

/** Исполнитель: аватар, имя для чтения с экрана и метка Лео, если его назначил Лео. */
export function CardAssignee({ card }: { card: Card }) {
  if (!card.assignee) return null;
  return (
    <span className="ms-auto flex min-w-0 items-center gap-1">
      <OwnerAvatar owner={card.assignee} />
      <span className="sr-only">{card.assignee.name}</span>
      {card.leo_fields.includes("assignee") ? <LeoMark /> : null}
    </span>
  );
}

function Count({
  icon: Icon,
  count,
  kind,
}: {
  icon: typeof Paperclip;
  count: number;
  kind: "attachments" | "comments";
}) {
  const t = useTranslations("kanban");
  const format = useFormatter();
  return (
    <span className="flex items-center gap-1">
      <Icon className="size-3.5" aria-hidden="true" />
      <span aria-hidden="true">{format.number(count)}</span>
      <span className="sr-only">{t(`card.insights.${kind}`, { count })}</span>
    </span>
  );
}

/** Низ: чат-источник, ход подзадач, счётчики вложений и комментариев; `trailing` — в конце строки (исполнитель). */
export function CardFooter({ card, trailing }: { card: Card; trailing?: ReactNode }) {
  const t = useTranslations("kanban");
  if (!hasFooterFacts(card) && !trailing) return null;
  const hasSubtasks = card.subtasks_total > 0;
  const share = hasSubtasks ? (card.subtasks_done / card.subtasks_total) * 100 : 0;
  return (
    <div className="flex items-center gap-3 text-muted-foreground text-xs tabular-nums">
      {card.source_chat ? <ChatSourceLine source={card.source_chat} /> : null}
      {hasSubtasks ? (
        <span className="flex items-center gap-1.5">
          <span className="h-1 w-10 overflow-hidden rounded-full bg-muted" aria-hidden="true">
            <span className="block h-full rounded-full bg-primary" style={{ width: `${share}%` }} />
          </span>
          <span aria-hidden="true">{t("card.subtasks", { done: card.subtasks_done, total: card.subtasks_total })}</span>
          <span className="sr-only">
            {t("card.subtasksLabel", { done: card.subtasks_done, total: card.subtasks_total })}
          </span>
        </span>
      ) : null}
      {card.attachment_count > 0 ? <Count icon={Paperclip} count={card.attachment_count} kind="attachments" /> : null}
      {card.comment_count > 0 ? <Count icon={MessageSquare} count={card.comment_count} kind="comments" /> : null}
      {trailing}
    </div>
  );
}
