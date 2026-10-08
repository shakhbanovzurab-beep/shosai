"use client";

import { type FormEvent, useState } from "react";

import { Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { FieldDescription, FieldLabel } from "@/components/ui/field-text";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";

import { COMMENT_MAX } from "../domain/contract";
import { usePlatformPrompts } from "../model/platform-prompts-provider";

/** Publishing turns the draft into a numbered version that every user gets from their next message. */
export function PublishDialog() {
  const {
    state: { published },
    actions: { publish },
    meta: { hasUnpublishedChanges, invalidReason, busy },
  } = usePlatformPrompts();
  const [open, setOpen] = useState(false);
  const [comment, setComment] = useState("");
  const canPublish = hasUnpublishedChanges && !invalidReason && !busy;
  const nextNumber = (published?.number ?? 0) + 1;

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!comment.trim()) return;
    if (await publish(comment.trim())) {
      setComment("");
      setOpen(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" disabled={!canPublish} className="self-start sm:self-auto">
          <Upload data-icon="inline-start" />
          Опубликовать
        </Button>
      </DialogTrigger>
      <DialogContent showCloseButton={false}>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>Опубликовать версию {nextNumber}</DialogTitle>
            <DialogDescription>
              Черновик станет действующей версией для всех пользователей Leo. Предыдущие версии останутся в истории, к
              ним можно откатиться.
            </DialogDescription>
          </DialogHeader>
          <Field>
            <FieldLabel htmlFor="publish-comment">Что изменилось</FieldLabel>
            <Textarea
              id="publish-comment"
              value={comment}
              onChange={(event) => setComment(event.currentTarget.value)}
              maxLength={COMMENT_MAX}
              placeholder="Например: ужесточили правила для платежей…"
              className="min-h-24"
              required
              autoFocus
            />
            <FieldDescription>
              {comment.length} / {COMMENT_MAX}
            </FieldDescription>
          </Field>
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline" disabled={busy}>
                Отмена
              </Button>
            </DialogClose>
            <Button type="submit" disabled={busy || !comment.trim()}>
              {busy ? <Spinner data-icon="inline-start" /> : null}
              Опубликовать
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
