"use client";

import { useId, useState } from "react";

import { useFormatter, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";

import type { ChatDigest, DigestSection } from "../../domain/digest-contract";
import { SECTION_PREVIEW } from "../../domain/digest-rules";
import { DigestItemRow } from "./digest-item";
import { MakeAllPromises } from "./digest-tasks";

/** Раздел дайджеста: первые пять пунктов и «Показать все»; под обещаниями — все свободные в одну карточку. */
export function DigestSectionView({ digest, section }: { digest: ChatDigest; section: DigestSection }) {
  const t = useTranslations("chatsDigest");
  const format = useFormatter();
  const [expanded, setExpanded] = useState(false);
  const heading = useId();
  const items = digest[section];
  if (items.length === 0) return null;
  const shown = expanded ? items : items.slice(0, SECTION_PREVIEW);
  return (
    <section aria-labelledby={heading} className="flex flex-col">
      <h4 id={heading} className="flex items-baseline gap-2 font-medium text-sm">
        {t(`sections.${section}`)}
        <span className="text-muted-foreground text-xs tabular-nums">{format.number(items.length)}</span>
      </h4>
      <ul className="divide-y">
        {shown.map((item) => (
          <DigestItemRow key={item.id} item={item} messenger={digest.chat.messenger} />
        ))}
      </ul>
      {items.length > SECTION_PREVIEW || section === "promises" ? (
        <div className="flex flex-wrap items-center gap-2 empty:hidden">
          {items.length > SECTION_PREVIEW ? (
            <Button variant="ghost" size="sm" aria-expanded={expanded} onClick={() => setExpanded((open) => !open)}>
              {expanded ? t("showFewer") : t("showAll", { count: items.length })}
            </Button>
          ) : null}
          {section === "promises" ? <MakeAllPromises digest={digest} /> : null}
        </div>
      ) : null}
    </section>
  );
}
