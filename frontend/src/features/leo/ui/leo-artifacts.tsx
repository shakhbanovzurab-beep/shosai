"use client";

import { useTranslations } from "use-intl";

import { LazyChatDigestCard } from "@/features/chats/ui/digest/lazy-digest-card";

import type { ChatDigestArtifact, LeoArtifact } from "../domain/artifacts";
import type { LeoProposal } from "../domain/proposals";
import { digestTaskHost } from "../model/digest-tasks";

const isChatDigest = (artifact: LeoArtifact): artifact is ChatDigestArtifact => artifact.kind === "chat_digest";

/**
 * Артефакты ответа (Leo §13.2) — после текста Leo, перед карточками одобрения. Дайджест чата рисует слайс chats;
 * его «Сделать задачей» кладёт карточку одобрения в этот ответ.
 */
export function LeoArtifacts({
  artifacts,
  onProposal,
}: {
  artifacts: LeoArtifact[];
  onProposal: (proposal: LeoProposal) => void;
}) {
  const t = useTranslations("chatsDigest");
  const ta = useTranslations("chatsApi");
  // Графики рисует виджет админ-панели (agent шаг 16c); в панели человека их не бывает.
  return artifacts.filter(isChatDigest).map((artifact) => {
    const digest = { workspaceId: artifact.workspace_id, chatId: artifact.chat_id, digestId: artifact.ref };
    const host = digestTaskHost(digest, onProposal, { failed: t("task.failed"), ta });
    return <LazyChatDigestCard key={artifact.ref} digest={digest} label={artifact.alt} host={host} />;
  });
}
