"use client";

import { Fragment, useState } from "react";

import { EllipsisVertical, Pencil, Trash2 } from "lucide-react";
import { useFormatter, useNow, useTranslations } from "use-intl";

import { Bubble, BubbleContent } from "@/components/ui/bubble";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu-items";
import { Message, MessageContent, MessageFooter, MessageHeader } from "@/components/ui/message";
import { Textarea } from "@/components/ui/textarea";

import { COMMENT_MAX, type Comment } from "../../domain/tasks-contract";
import { isLocalId } from "../../model/task-sync";
import { OwnerAvatar } from "../task-owner";
import { linkParts } from "./link-parts";

type CommentEdits = {
  edit: (comment: Comment, body: string) => Promise<boolean>;
  remove: (comment: Comment, message: string) => void;
};

/** Текст комментария: как написан, со ссылками. */
function CommentText({ body }: { body: string }) {
  return (
    <p dir="auto" className="whitespace-pre-wrap">
      {linkParts(body).map((part) =>
        part.href ? (
          <a
            key={part.start}
            href={part.href}
            target="_blank"
            rel="noopener noreferrer nofollow"
            className="underline underline-offset-2"
          >
            {part.text}
          </a>
        ) : (
          <Fragment key={part.start}>{part.text}</Fragment>
        ),
      )}
    </p>
  );
}

/** Правка своего комментария: Ctrl/⌘+Enter сохраняет, Esc отменяет. */
function CommentEditor({ comment, onDone, edits }: { comment: Comment; onDone: () => void; edits: CommentEdits }) {
  const t = useTranslations("kanbanPanel");
  const tc = useTranslations("common");
  // Текст живёт в самом поле; здесь — только пусто ли оно, чтобы не дать сохранить пустой комментарий.
  const [empty, setEmpty] = useState(false);
  const save = (form: HTMLFormElement) => {
    const next = String(new FormData(form).get("body") ?? "").trim();
    if (!next) return;
    onDone();
    void edits.edit(comment, next);
  };
  return (
    <form
      className="flex flex-col gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        save(event.currentTarget);
      }}
    >
      <Textarea
        name="body"
        defaultValue={comment.body}
        maxLength={COMMENT_MAX}
        dir="auto"
        aria-label={t("comments.editLabel")}
        className="field-sizing-content min-h-16"
        autoFocus
        onChange={(event) => setEmpty(!event.currentTarget.value.trim())}
        onKeyDown={(event) => {
          if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
            event.preventDefault();
            event.currentTarget.form?.requestSubmit();
          }
          if (event.key === "Escape") onDone();
        }}
      />
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={empty}>
          {tc("actions.save")}
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onDone}>
          {tc("actions.cancel")}
        </Button>
      </div>
    </form>
  );
}

function CommentMenu({ onEdit, onDelete }: { onEdit: () => void; onDelete: () => void }) {
  const t = useTranslations("kanbanPanel");
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon-xs"
          aria-label={t("comments.actions")}
          className="ms-auto opacity-0 pointer-coarse:opacity-100 focus-visible:opacity-100 group-hover/message:opacity-100 data-[state=open]:opacity-100"
        >
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-max min-w-40">
        <DropdownMenuGroup>
          <DropdownMenuItem onSelect={onEdit}>
            <Pencil />
            {t("comments.edit")}
          </DropdownMenuItem>
          <DropdownMenuItem variant="destructive" onSelect={onDelete}>
            <Trash2 />
            {t("comments.delete")}
          </DropdownMenuItem>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** Комментарий: кто, когда, текст; свой можно поправить и удалить. Свой неотправленный — «Отправляется…». */
export function CommentMessage({ comment, edits }: { comment: Comment; edits: CommentEdits }) {
  const t = useTranslations("kanbanPanel");
  const format = useFormatter();
  const now = useNow({ updateInterval: 60_000 });
  const [editing, setEditing] = useState(false);
  const pending = isLocalId(comment.id);
  const created = new Date(comment.created_at);
  return (
    <Message>
      <MessageContent className="gap-1.5">
        <MessageHeader className="gap-2 px-0">
          <OwnerAvatar owner={comment.author} />
          <span dir="auto" className="truncate text-foreground">
            {comment.author.name}
          </span>
          <time
            dateTime={comment.created_at}
            title={format.dateTime(created, { dateStyle: "medium", timeStyle: "short" })}
          >
            {format.relativeTime(created, now)}
          </time>
          {comment.edited_at ? <span>· {t("comments.edited")}</span> : null}
          {comment.author.is_you && !pending && !editing ? (
            <CommentMenu
              onEdit={() => setEditing(true)}
              onDelete={() => edits.remove(comment, t("comments.deleted"))}
            />
          ) : null}
        </MessageHeader>
        {editing ? (
          <CommentEditor comment={comment} edits={edits} onDone={() => setEditing(false)} />
        ) : (
          <Bubble variant="muted" className="max-w-full">
            <BubbleContent>
              <CommentText body={comment.body} />
            </BubbleContent>
          </Bubble>
        )}
        {pending ? <MessageFooter className="px-0">{t("comments.sending")}</MessageFooter> : null}
      </MessageContent>
    </Message>
  );
}
