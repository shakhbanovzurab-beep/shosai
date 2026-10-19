"use client";

import { useId, useState } from "react";

import { ThinkingOrb } from "thinking-orbs";
import { useFormatter, useNow, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Item, ItemActions, ItemContent, ItemDescription, ItemGroup, ItemMedia, ItemTitle } from "@/components/ui/item";

import { isPending, type LeoProposal } from "../domain/proposals";
import { usePendingProposals } from "../model/proposals";
import { LeoProposalCard } from "./proposal/leo-proposal";

function ProposalRow({ proposal, onOpen }: { proposal: LeoProposal; onOpen: () => void }) {
  const t = useTranslations("leoCards");
  const format = useFormatter();
  const now = useNow({ updateInterval: 60_000 });
  const { kind, app } = proposal.origin;
  const origin = kind === "mcp" ? t("card.origin.mcp", { app: app ?? "MCP" }) : t(`card.origin.${kind}`);
  return (
    <Item role="listitem" variant="outline" size="sm">
      <ItemMedia aria-hidden="true" className="[&_canvas]:size-5!">
        <ThinkingOrb state="breathing" size={20} />
      </ItemMedia>
      <ItemContent className="min-w-48">
        <ItemTitle dir="auto" className="line-clamp-none">
          {proposal.title}
        </ItemTitle>
        <ItemDescription className="text-xs">
          {origin} · {t("card.expires", { time: format.relativeTime(new Date(proposal.expires_at), now) })}
        </ItemDescription>
      </ItemContent>
      <ItemActions className="ms-auto">
        <Button variant="outline" size="sm" onClick={onOpen}>
          {t("inbox.review")}
        </Button>
      </ItemActions>
    </Item>
  );
}

/**
 * «Нужны вы» на главной: всё, что ждёт решения человека, — из чатов, поручений и MCP (Leo §13.3, approvals
 * inbox). Пусто — блока нет: тихое пространство. Открытая строка становится той же карточкой, что в чате.
 */
export function NeedsYou() {
  const t = useTranslations("leoCards");
  const headingId = useId();
  const state = usePendingProposals();
  // Открытое предложение держится и после решения: карточка свернётся в строку итога на своём месте.
  const [open, setOpen] = useState<LeoProposal | null>(null);
  const pending = state.status === "ready" ? state.data.actions.filter(isPending) : [];
  const decided = open && !pending.some((p) => p.id === open.id) ? open : null;
  if (pending.length === 0 && !decided) return null;

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <h2 id={headingId} className="flex items-baseline gap-2 font-medium text-lg">
          {t("inbox.title")}
          <span className="font-normal text-muted-foreground text-sm tabular-nums">{pending.length}</span>
        </h2>
        <p className="text-muted-foreground text-sm">{t("inbox.description")}</p>
      </div>
      <ItemGroup>
        {decided ? <LeoProposalCard proposal={decided} /> : null}
        {pending.map((proposal) =>
          open?.id === proposal.id ? (
            <LeoProposalCard key={proposal.id} proposal={proposal} />
          ) : (
            <ProposalRow key={proposal.id} proposal={proposal} onOpen={() => setOpen(proposal)} />
          ),
        )}
      </ItemGroup>
    </section>
  );
}
