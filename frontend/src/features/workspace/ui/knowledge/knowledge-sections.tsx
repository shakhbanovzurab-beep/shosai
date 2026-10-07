"use client";

import type { ReactNode } from "react";

import { BookOpen, FilterX } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";

import { isSource } from "../../domain/knowledge";
import type { KnowledgeItem } from "../../domain/knowledge-contract";
import { EmptyMessage } from "../shared/empty-message";
import { QuietEmpty, TeamSection } from "../shared/layout";
import { type KnowledgeCtx, KnowledgeRow } from "./knowledge-row";

function KnowledgeList({ items, ctx, label }: { items: KnowledgeItem[]; ctx: KnowledgeCtx; label: string }) {
  return (
    <ul className="divide-y rounded-xl border bg-card" aria-label={label}>
      {items.map((item) => (
        <KnowledgeRow key={item.id} item={item} ctx={ctx} showProject />
      ))}
    </ul>
  );
}

type Props = {
  all: KnowledgeItem[];
  shown: KnowledgeItem[];
  ctx: KnowledgeCtx;
  addMenu: ReactNode;
  onClearFilters: () => void;
};

/** Files, then connected sources; or what to do when there is nothing yet, or nothing matches. */
export function KnowledgeSections({ all, shown, ctx, addMenu, onClearFilters }: Props) {
  const t = useTranslations("workspaceKnowledge");
  if (all.length === 0)
    return (
      <EmptyMessage
        icon={BookOpen}
        title={t("empty.title")}
        text={t("empty.text", { workspace: ctx.workspaceName })}
        action={addMenu}
      />
    );
  if (shown.length === 0)
    return (
      <EmptyMessage
        icon={FilterX}
        title={t("noMatch.title")}
        text={t("noMatch.text")}
        action={
          <Button variant="outline" onClick={onClearFilters}>
            {t("noMatch.clear")}
          </Button>
        }
      />
    );
  const files = shown.filter((item) => !isSource(item));
  const sources = shown.filter(isSource);
  return (
    <>
      <TeamSection id="knowledge-files" title={t("sections.files", { count: files.length })}>
        {files.length ? (
          <KnowledgeList items={files} ctx={ctx} label={t("sections.filesLabel")} />
        ) : (
          <QuietEmpty>{t("sections.noFilesMatch")}</QuietEmpty>
        )}
      </TeamSection>
      <TeamSection id="knowledge-sources" title={t("sections.sources", { count: sources.length })}>
        {sources.length ? (
          <KnowledgeList items={sources} ctx={ctx} label={t("sections.sourcesLabel")} />
        ) : (
          <QuietEmpty>{ctx.admin ? t("sections.sourcesEmptyAdmin") : t("sections.sourcesEmpty")}</QuietEmpty>
        )}
      </TeamSection>
    </>
  );
}
