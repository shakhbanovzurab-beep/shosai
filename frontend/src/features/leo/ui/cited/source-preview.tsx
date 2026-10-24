"use client";

import { Fragment } from "react";

import { Copy, X } from "lucide-react";
import { toast } from "sonner";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { copyText } from "@/lib/copy-text";

import { type LeoSource, quoteParts } from "../../domain/sources";
import { SOURCE_ICONS } from "./source-icons";

/** Отрывок с выделенными словами, которые подтверждают ответ. */
function Quote({ quote, highlight }: { quote: string; highlight: string[] }) {
  return (
    <>
      {quoteParts(quote, highlight).map((part) =>
        part.lit ? (
          <mark key={part.at} className="rounded-sm bg-primary/15 px-0.5 text-foreground">
            {part.text}
          </mark>
        ) : (
          <Fragment key={part.at}>{part.text}</Fragment>
        ),
      )}
    </>
  );
}

/** Раскрытый источник: откуда (пространство, место в записи), название и тот самый отрывок. */
export function SourcePreview({ source, index, onClose }: { source: LeoSource; index: number; onClose: () => void }) {
  const t = useTranslations("leoCards");
  const common = useTranslations("common");
  const Icon = SOURCE_ICONS[source.kind];
  const copy = async () => {
    try {
      await copyText(source.quote);
      toast.success(t("sources.copied"));
    } catch {
      toast.error(t("sources.copyFailed"));
    }
  };
  return (
    <section
      aria-label={t("sources.marker", { index, title: source.title })}
      className="flex flex-col gap-2 rounded-xl border bg-muted/30 p-3"
    >
      <div className="flex items-start gap-2">
        <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="font-medium text-sm" dir="auto">
            {source.title}
          </span>
          <span className="text-muted-foreground text-xs">
            {source.locator ? t("sources.at", { space: source.space, locator: source.locator }) : source.space}
          </span>
        </div>
        <Button variant="ghost" size="icon-xs" aria-label={common("actions.close")} onClick={onClose}>
          <X />
        </Button>
      </div>
      {/* Источник без отрывка (задача, найденный файл) — только название и пространство. */}
      {source.quote ? (
        <>
          <blockquote dir="auto" className="border-s-2 ps-3 text-sm leading-relaxed">
            <Quote quote={source.quote} highlight={source.highlight} />
          </blockquote>
          <Button variant="ghost" size="xs" className="self-start" onClick={() => void copy()}>
            <Copy data-icon="inline-start" />
            {t("sources.copy")}
          </Button>
        </>
      ) : null}
    </section>
  );
}
