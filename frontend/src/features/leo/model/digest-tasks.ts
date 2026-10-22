"use client";

import { toast } from "sonner";

import type { DigestRef } from "@/features/chats/domain/digest-contract";
import { chatsProblemOf } from "@/features/chats/domain/problems";
import { type DigestTaskHost, digestResource } from "@/features/chats/model/digests";
import { type ApiWords, describeProblem } from "@/features/chats/model/words";

import { proposalsApi } from "../api/proposals-api";
import { type LeoProposal, proposalCardId } from "../domain/proposals";
import { proposalArrived } from "./proposals";

/*
 * «Сделать задачей» из дайджеста в разговоре Leo (CF-D5, AG-R2): сервер кладёт карточку `tasks.create` в эту же
 * переписку без вызова модели, разговор показывает её под ответом, «Ждёт вашего одобрения» ведёт к ней.
 */

/** Показать карточку одобрения: прокрутить к ней и дать ей фокус, плавно — только без «уменьшить движение». */
function showProposal(proposalId: string) {
  const card = document.getElementById(proposalCardId(proposalId));
  if (!card) return;
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  card.scrollIntoView({ block: "nearest", behavior: still ? "auto" : "smooth" });
  card.focus({ preventScroll: true });
}

export function digestTaskHost(
  digest: DigestRef,
  onProposal: (proposal: LeoProposal) => void,
  words: { failed: string; ta: ApiWords },
): DigestTaskHost {
  return {
    async makeTasks(itemIds) {
      try {
        const proposal = await proposalsApi.fromDigest(digest, itemIds);
        onProposal(proposal);
        proposalArrived();
        return proposal.id;
      } catch (error) {
        toast.error(words.failed, { description: describeProblem(error, words.ta) });
        // Пункт уже взят другой карточкой (другая вкладка): дайджест покажет, какой.
        if (chatsProblemOf(error) === "item_already_proposed") void digestResource(digest).reload();
        return null;
      }
    },
    showProposal,
  };
}
