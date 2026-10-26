"use client";

import * as React from "react";

import { cn } from "cn";
import { useTranslations } from "use-intl";

import { shownTitle } from "../domain/report-titles";
import { type LeoSource, pageHref } from "../domain/sources";
import { SOURCE_ICONS } from "./cited/source-icons";

// Сколько источников видно сразу; остальные за фишкой «Ещё N».
const SHOWN = 4;
const CHIP = "inline-flex h-6.5 max-w-52 items-center gap-1.5 rounded-md border bg-card px-2 text-xs shadow-xs";

/** Источники хода на ленте «думает»: фишки появляются по одной, страница сети открывается по ссылке. */
export function LeoStepSources({ sources }: { readonly sources: LeoSource[] }) {
  const t = useTranslations("leo");
  const tCards = useTranslations("leoCards");
  const [showAll, setShowAll] = React.useState(false);
  const shown = showAll ? sources : sources.slice(0, SHOWN);
  const hidden = sources.length - shown.length;

  return (
    <>
      <span className="text-muted-foreground text-sm">{tCards("sources.count", { count: sources.length })}</span>
      <ul className="flex flex-wrap gap-1.5">
        {shown.map((source, index) => (
          <li
            key={`${source.kind}:${source.id}:${source.locator ?? ""}`}
            className="fade-in zoom-in-95 animate-in fill-mode-both duration-200 motion-reduce:animate-none"
            style={{ animationDelay: `${index * 60}ms` }}
          >
            <SourceChip source={source} />
          </li>
        ))}
        {hidden > 0 ? (
          <li>
            <button
              type="button"
              onClick={() => setShowAll(true)}
              className={cn(
                CHIP,
                "cursor-pointer text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring",
              )}
            >
              {t("steps.moreSources", { count: hidden })}
            </button>
          </li>
        ) : null}
      </ul>
    </>
  );
}

function SourceChip({ source }: { readonly source: LeoSource }) {
  const Icon = SOURCE_ICONS[source.kind];
  const href = pageHref(source);
  const content = (
    <>
      <Icon className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
      <span className="truncate" dir="auto">
        {shownTitle(source)}
      </span>
    </>
  );
  if (href === null) return <span className={CHIP}>{content}</span>;
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(CHIP, "outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring")}
    >
      {content}
    </a>
  );
}
