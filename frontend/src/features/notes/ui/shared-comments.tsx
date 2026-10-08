"use client";

import { type FormEvent, useTransition } from "react";

import { useFormatter, useTranslations } from "next-intl";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup } from "@/components/ui/field";
import { FieldLabel } from "@/components/ui/field-text";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { useNow } from "@/hooks/use-now";
import { getInitials } from "@/lib/utils";

import { SHARED_AUTHOR_MAX, SHARED_COMMENT_MAX } from "../domain/share-link";
import { postSharedComment, retrySharedComments, useSharedComments } from "../model/share-link";

/** Replies under a shared meeting: anyone with the link reads them and adds their own. */
export function SharedComments({ token }: { readonly token: string }) {
  const t = useTranslations("notesShare");
  const common = useTranslations("common");
  const format = useFormatter();
  // Comments load in the browser, so "5 minutes ago" is always worked out there, against the viewer's clock.
  // `now` ticks by the minute: a comment from this minute reads "now" rather than "in 20 seconds".
  const now = useNow();
  const state = useSharedComments(token);
  const [pending, startTransition] = useTransition();

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const text = String(data.get("comment") ?? "").trim();
    if (!text) return;
    startTransition(async () => {
      // A failed post keeps the text, so the reply can be sent again.
      if (!(await postSharedComment(token, String(data.get("author") ?? "").trim(), text, t))) return;
      const field = form.elements.namedItem("comment");
      if (field instanceof HTMLTextAreaElement) field.value = "";
    });
  };

  return (
    <section aria-labelledby="shared-comments-heading" className="flex flex-col gap-5 border-t pt-8">
      <h2 id="shared-comments-heading" className="font-medium text-lg">
        {t("comments.title")}
      </h2>
      {state.status === "loading" ? <Skeleton className="h-16" /> : null}
      {state.status === "error" ? (
        <p className="text-muted-foreground text-sm">
          {t("comments.loadFailed")}{" "}
          <button
            type="button"
            className="underline underline-offset-2"
            onClick={() => void retrySharedComments(token)}
          >
            {common("actions.retry")}
          </button>
        </p>
      ) : null}
      {state.status === "ready" && state.data.comments.length > 0 ? (
        <ol className="flex flex-col gap-5">
          {state.data.comments.map((comment) => (
            <li key={comment.id} className="flex gap-3">
              <Avatar size="sm" className="mt-0.5">
                <AvatarFallback>{getInitials(comment.author)}</AvatarFallback>
              </Avatar>
              <div className="flex min-w-0 flex-col gap-1">
                <div className="flex items-baseline gap-2">
                  <span dir="auto" className="font-medium text-sm">
                    {comment.author}
                  </span>
                  <time className="text-muted-foreground text-xs" dateTime={comment.createdAt}>
                    {now === null ? null : format.relativeTime(Math.min(Date.parse(comment.createdAt), now), now)}
                  </time>
                </div>
                <p dir="auto" className="whitespace-pre-wrap break-words text-sm leading-relaxed">
                  {comment.text}
                </p>
              </div>
            </li>
          ))}
        </ol>
      ) : null}
      <form onSubmit={submit} className="flex flex-col gap-3">
        <FieldGroup className="gap-3">
          <Field>
            <FieldLabel htmlFor="shared-comment">{t("comments.comment")}</FieldLabel>
            <Textarea
              id="shared-comment"
              name="comment"
              dir="auto"
              required
              maxLength={SHARED_COMMENT_MAX}
              placeholder={t("comments.commentPlaceholder")}
              className="min-h-24"
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="shared-author">{t("comments.name")}</FieldLabel>
            <Input
              id="shared-author"
              name="author"
              dir="auto"
              maxLength={SHARED_AUTHOR_MAX}
              autoComplete="name"
              placeholder={t("comments.namePlaceholder", { guest: t("comments.guest") })}
            />
          </Field>
        </FieldGroup>
        <Button type="submit" className="self-start" disabled={pending}>
          {pending ? <Spinner data-icon="inline-start" /> : null}
          {t("comments.post")}
        </Button>
      </form>
    </section>
  );
}
