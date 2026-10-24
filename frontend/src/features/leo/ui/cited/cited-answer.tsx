"use client";

import { useState } from "react";

import { cn } from "cn";
import { useTranslations } from "use-intl";

import { citesIn } from "../../domain/markdown-cites";
import type { LeoSource } from "../../domain/sources";
import { type Citations, CitationsContext } from "../markdown/citations";
import { LeoMarkdown, type PartMark } from "../markdown/leo-markdown";
import { SOURCE_ICONS } from "./source-icons";
import { SourcePreview } from "./source-preview";

type Focus = { lit: number | null; open: number | null };

/** Номер источника после предложения: наведение подсвечивает предложение, нажатие раскрывает отрывок. */
function Marker({
  n,
  source,
  focus,
  onLight,
  onOpen,
}: {
  n: number;
  source: LeoSource;
  focus: Focus;
  onLight: (n: number | null) => void;
  onOpen: (n: number) => void;
}) {
  const t = useTranslations("leoCards");
  return (
    <button
      type="button"
      aria-label={t("sources.marker", { index: n, title: source.title })}
      aria-expanded={focus.open === n}
      onMouseEnter={() => onLight(n)}
      onMouseLeave={() => onLight(null)}
      onFocus={() => onLight(n)}
      onBlur={() => onLight(null)}
      onClick={() => onOpen(n)}
      className={cn(
        "mx-0.5 inline-grid min-w-4 cursor-pointer place-items-center rounded-sm bg-muted px-1 align-text-top text-[0.65rem] text-muted-foreground tabular-nums outline-none focus-visible:ring-2 focus-visible:ring-ring",
        (focus.lit === n || focus.open === n) && "bg-primary text-primary-foreground",
      )}
    >
      {n}
    </button>
  );
}

/**
 * Ответ Leo, связанный с источниками (Cited Answer): в тексте — маркеры, под ответом — источники. Точка на маркере
 * или источнике подсвечивает блоки ответа, которые на него опираются, и приглушает остальное.
 */
export function CitedAnswer({
  text,
  sources,
  isStreaming,
}: {
  text: string;
  sources: LeoSource[];
  isStreaming: boolean;
}) {
  const t = useTranslations("leoCards");
  const [focus, setFocus] = useState<Focus>({ lit: null, open: null });
  const light = (lit: number | null) => setFocus((f) => ({ ...f, lit }));
  const open = (n: number) => setFocus((f) => ({ ...f, open: f.open === n ? null : n }));
  const active = focus.lit ?? focus.open;
  const opened = focus.open === null ? null : sources[focus.open - 1];
  const citations: Citations = {
    count: sources.length,
    marker: (n) => <Marker n={n} source={sources[n - 1]} focus={focus} onLight={light} onOpen={open} />,
  };
  const mark: PartMark | undefined =
    active === null ? undefined : (part) => (citesIn(part.blocks, sources.length).has(active) ? "lit" : "dim");

  return (
    <div className="flex flex-col gap-3">
      <CitationsContext value={citations}>
        <LeoMarkdown text={text} mark={mark} />
      </CitationsContext>
      {isStreaming ? null : (
        <div className="flex flex-col gap-2">
          <span className="text-muted-foreground text-xs">{t("sources.count", { count: sources.length })}</span>
          <ul className="flex flex-wrap gap-1.5">
            {sources.map((source, index) => {
              const Icon = SOURCE_ICONS[source.kind];
              const n = index + 1;
              return (
                <li key={`${source.kind}:${source.id}:${source.locator ?? ""}`}>
                  <button
                    type="button"
                    aria-expanded={focus.open === n}
                    onMouseEnter={() => light(n)}
                    onMouseLeave={() => light(null)}
                    onClick={() => open(n)}
                    className={cn(
                      "flex max-w-56 cursor-pointer items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring",
                      focus.open === n && "bg-muted",
                    )}
                  >
                    <Icon className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                    <span className="truncate" dir="auto">
                      {source.title}
                    </span>
                    <span className="text-muted-foreground tabular-nums">{n}</span>
                  </button>
                </li>
              );
            })}
          </ul>
          {opened ? (
            <SourcePreview
              source={opened}
              index={focus.open ?? 0}
              onClose={() => setFocus({ lit: null, open: null })}
            />
          ) : null}
        </div>
      )}
    </div>
  );
}
