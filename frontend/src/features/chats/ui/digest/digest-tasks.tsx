"use client";

import { use } from "react";

import { CircleCheck } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { Link } from "@/lib/navigation";

import type { ChatDigest, DigestItem } from "../../domain/digest-contract";
import { freePromises, itemTask } from "../../domain/digest-rules";
import { type DigestTasks, DigestTasksContext } from "./digest-tasks-context";

/*
 * «Сделать задачей» внутри карточки дайджеста: что делать, решает разговор Leo (карточка одобрения, CF-D5),
 * карточка только показывает состояние пункта — свободен, готовится, ждёт одобрения, задача создана.
 */

function useDigestTasks(): DigestTasks {
  const tasks = use(DigestTasksContext);
  if (!tasks) throw new Error("DigestTasksContext is missing");
  return tasks;
}

export function ItemTaskAction({ item }: { item: DigestItem }) {
  const t = useTranslations("chatsDigest");
  const { making, make, showProposal } = useDigestTasks();
  const task = itemTask(item, making);
  switch (task.kind) {
    case "created":
      return (
        <span className="flex shrink-0 items-center gap-1.5 self-start text-muted-foreground text-xs">
          <CircleCheck className="size-3.5 text-emerald-600" aria-hidden="true" />
          {t("task.created")}
          <Link
            href={`/app/kanban?task=${encodeURIComponent(task.taskId)}`}
            className="font-medium text-foreground underline-offset-4 hover:underline"
          >
            {t("task.open")}
          </Link>
        </span>
      );
    case "waiting":
      return (
        <Button
          variant="link"
          size="sm"
          className="shrink-0 self-start px-0"
          onClick={() => showProposal(task.proposalId)}
        >
          {t("task.waiting")}
        </Button>
      );
    default:
      return (
        <Button
          variant="outline"
          size="sm"
          className="shrink-0 self-start"
          disabled={task.kind === "making"}
          onClick={() => make([item.id])}
        >
          {task.kind === "making" ? <Spinner data-icon="inline-start" /> : null}
          {t("task.make")}
        </Button>
      );
  }
}

/** Все свободные обещания — в одну карточку одобрения. */
export function MakeAllPromises({ digest }: { digest: ChatDigest }) {
  const t = useTranslations("chatsDigest");
  const { making, make } = useDigestTasks();
  const free = freePromises(digest);
  if (free.length < 2) return null;
  return (
    <Button
      variant="outline"
      size="sm"
      className="self-start"
      disabled={making.size > 0}
      onClick={() => make(free.map((promise) => promise.id))}
    >
      {t("task.makeAll", { count: free.length })}
    </Button>
  );
}
