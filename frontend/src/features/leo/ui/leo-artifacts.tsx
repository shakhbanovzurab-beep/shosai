"use client";

import { useTranslations } from "use-intl";

import { LazyChatDigestCard } from "@/features/chats/ui/digest/lazy-digest-card";
import { lazyComponent } from "@/lib/lazy-component";

import type { LeoArtifact } from "../domain/artifacts";
import type { LeoProposal } from "../domain/proposals";
import { digestTaskHost } from "../model/digest-tasks";
import { LeoImage } from "./leo-image";

// График с recharts — свой чанк; пока он грузится, место под него уже занято, и ответ не прыгает.
const LeoChart = lazyComponent(() => import("./chart/leo-chart").then((module) => module.LeoChart), {
  loading: () => <div className="h-[17.25rem] rounded-lg border" aria-hidden="true" />,
});

/**
 * Артефакты ответа (Leo §13.2) — после текста Leo, перед карточками одобрения. Дайджест чата рисует слайс chats;
 * его «Сделать задачей» кладёт карточку одобрения в этот ответ. График и картинка бывают только в ответе оператору.
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
  return artifacts.map((artifact) => {
    if (artifact.kind === "chart") return <LeoChart key={artifact.ref} chart={artifact} />;
    if (artifact.kind === "image") return <LeoImage key={artifact.ref} image={artifact} />;
    const digest = { workspaceId: artifact.workspace_id, chatId: artifact.chat_id, digestId: artifact.ref };
    const host = digestTaskHost(digest, onProposal, { failed: t("task.failed"), ta });
    return <LazyChatDigestCard key={artifact.ref} digest={digest} label={artifact.alt} host={host} />;
  });
}
