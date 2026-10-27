"use client";

import { useState } from "react";

import { useTranslations } from "use-intl";

import { changeIndexes, isPending, type LeoProposal } from "../../domain/proposals";
import { useProposal } from "../../model/proposal-store";
import { approveProposal, rejectProposal } from "../../model/proposals";
import {
  ActionCardActions,
  ActionCardHeader,
  ActionCardRoot,
  ActionCardSuspicion,
  ActionCardTaint,
} from "./action-card";
import { ActionCardResolved } from "./action-card-resolved";
import { FieldsPreview } from "./fields-preview";
import { InlineDiff } from "./inline-diff";

/**
 * Предложенное действие Leo — в чате и в «Нужны вы»: карточка, пока ждёт решения, затем строка итога. Для правки
 * текста человек выбирает, какие замены взять; «Применить» отправляет только их.
 */
export function LeoProposalCard({ proposal: sent }: { proposal: LeoProposal }) {
  const t = useTranslations("leoCards");
  const { proposal, busy } = useProposal(sent);
  // Храним отклонённые замены: принятые — все остальные, поэтому начальное состояние не зависит от пропса.
  const [declined, setDeclined] = useState<ReadonlySet<number>>(() => new Set());

  if (!isPending(proposal)) return <ActionCardResolved proposal={proposal} />;

  const diff = proposal.preview.kind === "diff" ? proposal.preview : null;
  const all = diff ? changeIndexes(diff.segments) : [];
  const accepted = new Set(all.filter((index) => !declined.has(index)));
  const words = { failed: t("card.failed") };
  // Клавиши карточки работают и при занятых кнопках: решение, которое уже ждёт ответа, не уходит второй раз.
  const approve = () => {
    if (busy || (diff && accepted.size === 0)) return;
    void approveProposal(proposal, diff ? [...accepted] : undefined, words);
  };
  const reject = () => {
    if (!busy) void rejectProposal(proposal, words);
  };
  const toggle = (index: number) =>
    setDeclined((current) => {
      const next = new Set(current);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });

  return (
    <ActionCardRoot proposal={proposal} onApprove={approve} onReject={reject}>
      <ActionCardHeader proposal={proposal} />
      {proposal.preview.kind === "diff" ? (
        <InlineDiff
          target={proposal.preview.target}
          segments={proposal.preview.segments}
          accepted={accepted}
          onToggle={toggle}
          onAll={(take) => setDeclined(take ? new Set() : new Set(all))}
        />
      ) : (
        <FieldsPreview fields={proposal.preview.fields} body={proposal.preview.body} />
      )}
      {proposal.suspicious ? <ActionCardSuspicion /> : null}
      <ActionCardTaint label={proposal.taint} />
      <ActionCardActions
        proposal={proposal}
        busy={busy}
        approveDisabled={diff !== null && accepted.size === 0}
        approveLabel={diff ? t("diff.apply", { count: accepted.size }) : t("card.approve")}
        onApprove={approve}
        onReject={reject}
      />
    </ActionCardRoot>
  );
}
