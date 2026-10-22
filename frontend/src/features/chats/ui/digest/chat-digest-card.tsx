"use client";

import { useState } from "react";

import { isNotFound } from "@/lib/api/errors";

import type { DigestRef } from "../../domain/digest-contract";
import { type DigestTaskHost, digestResource, markItemsProposed, useDigest } from "../../model/digests";
import { DigestCard } from "./digest-card";
import { DigestFailed, DigestGone, DigestSkeleton } from "./digest-states";
import { type DigestTasks, DigestTasksContext } from "./digest-tasks-context";

/*
 * Дайджест чата в ответе Leo (артефакт `chat_digest`, CF-D11). Карточка своя у слайса chats; задачи из пунктов
 * делает разговор Leo — карточкой одобрения в той же переписке (CF-D5), поэтому он передаётся сюда снаружи.
 */

export function ChatDigestCard({ digest, label, host }: { digest: DigestRef; label: string; host: DigestTaskHost }) {
  const state = useDigest(digest);
  const [making, setMaking] = useState<ReadonlySet<string>>(() => new Set());

  if (state.status === "loading") return <DigestSkeleton label={label} />;
  if (state.status === "error")
    return isNotFound(state.cause) ? (
      <DigestGone label={label} />
    ) : (
      <DigestFailed label={label} onRetry={() => void digestResource(digest).refresh()} />
    );

  const tasks: DigestTasks = {
    making,
    // Пункты готовятся независимо: второй запрос не сбрасывает спиннер первого.
    make: (itemIds) => {
      setMaking((current) => new Set([...current, ...itemIds]));
      void host.makeTasks(itemIds).then((proposalId) => {
        if (proposalId) markItemsProposed(digest, itemIds, proposalId);
        const done = new Set(itemIds);
        setMaking((current) => new Set([...current].filter((id) => !done.has(id))));
      });
    },
    showProposal: host.showProposal,
  };
  return (
    <DigestTasksContext value={tasks}>
      <DigestCard digest={state.data} label={label} />
    </DigestTasksContext>
  );
}
