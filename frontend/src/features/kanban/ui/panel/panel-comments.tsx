"use client";

import { useId, useState } from "react";

import { ArrowDown } from "lucide-react";
import { toast } from "sonner";
import { useFormatter, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import {
  MessageScroller,
  MessageScrollerButton,
  MessageScrollerContent,
  MessageScrollerItem,
  MessageScrollerProvider,
  MessageScrollerViewport,
} from "@/components/ui/message-scroller";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";

import type { CommentsPage } from "../../domain/tasks-contract";
import { commentsResource, loadEarlierComments, useComments } from "../../model/comments-resource";
import { CommentComposer } from "./comment-composer";
import { CommentMessage } from "./comment-message";
import { useCommentActions } from "./use-panel-actions";

/** «Показать ранее»: следующая страница старых комментариев встаёт сверху, прокрутка остаётся на месте. */
function ShowEarlier({ taskId }: { taskId: string }) {
  const t = useTranslations("kanbanPanel");
  const [loading, setLoading] = useState(false);
  const load = () => {
    setLoading(true);
    loadEarlierComments(taskId)
      .catch(() => toast.error(t("comments.earlierFailed")))
      .finally(() => setLoading(false));
  };
  return (
    <Button variant="ghost" size="sm" className="self-center" disabled={loading} onClick={load}>
      {loading ? <Spinner data-icon="inline-start" /> : null}
      {t("comments.earlier")}
    </Button>
  );
}

/** Ветка: старые сверху, последние видны сразу; длинная прокручивается внутри своей рамки. */
function CommentThread({ taskId, page }: { taskId: string; page: CommentsPage }) {
  const t = useTranslations("kanbanPanel");
  const actions = useCommentActions(taskId);
  const oldestFirst = page.items.toReversed();
  if (oldestFirst.length === 0) return <p className="text-muted-foreground text-sm">{t("comments.empty")}</p>;
  return (
    <MessageScrollerProvider autoScroll defaultScrollPosition="end">
      {/* Рамка по высоте ветки, не выше 28rem: короткая ветка без пустого места, длинная прокручивается. */}
      <MessageScroller className="h-auto max-h-[28rem] rounded-lg border">
        <MessageScrollerViewport aria-label={t("comments.label")} preserveScrollOnPrepend className="max-h-[28rem]">
          <MessageScrollerContent className="min-h-0 gap-4 p-3">
            {page.next_cursor ? <ShowEarlier taskId={taskId} /> : null}
            {oldestFirst.map((comment) => (
              <MessageScrollerItem key={comment.id} messageId={comment.id}>
                <CommentMessage comment={comment} edits={actions} />
              </MessageScrollerItem>
            ))}
          </MessageScrollerContent>
        </MessageScrollerViewport>
        <MessageScrollerButton>
          <ArrowDown />
          <span className="sr-only">{t("comments.latest")}</span>
        </MessageScrollerButton>
      </MessageScroller>
    </MessageScrollerProvider>
  );
}

/** Комментарии задачи: ветка и поле для нового. */
export function PanelComments({ taskId, count }: { taskId: string; count: number }) {
  const t = useTranslations("kanbanPanel");
  const tc = useTranslations("common");
  const format = useFormatter();
  const state = useComments(taskId);
  const actions = useCommentActions(taskId);
  const headingId = useId();
  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-3">
      <h3 id={headingId} className="flex items-center gap-2 font-medium text-sm">
        {t("comments.label")}
        {count > 0 ? <span className="text-muted-foreground tabular-nums">{format.number(count)}</span> : null}
      </h3>
      {state.status === "loading" ? (
        <div role="status" aria-label={t("comments.loading")} className="flex flex-col gap-2">
          <Skeleton className="h-12 w-3/4" />
          <Skeleton className="h-12 w-2/3" />
        </div>
      ) : null}
      {state.status === "error" ? (
        <div className="flex items-center gap-3 text-sm">
          <span className="text-muted-foreground">{t("comments.failed")}</span>
          <Button variant="outline" size="sm" onClick={() => void commentsResource(taskId).reload()}>
            {tc("actions.retry")}
          </Button>
        </div>
      ) : null}
      {state.status === "ready" ? <CommentThread taskId={taskId} page={state.data} /> : null}
      <CommentComposer onSend={actions.add} />
    </section>
  );
}
