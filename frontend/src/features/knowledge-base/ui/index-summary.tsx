"use client";

import { Boxes, Cpu, FileStack, Loader } from "lucide-react";
import { useFormatter, useLocale, useTranslations } from "next-intl";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatBytes } from "@/i18n/format-units";

import type { IndexResponse } from "../domain/contract";

type Totals = { files: number; chunks: number; processing: number; failed: number; bytes: number };

/** How much Leo uses (against the plan's limit), chunks, what is still being read, and how the index is built. */
export function IndexSummary({ totals, index }: { totals: Totals; index: IndexResponse | null }) {
  const t = useTranslations("knowledgeBase");
  const common = useTranslations("common");
  const format = useFormatter();
  const locale = useLocale();
  const limit = index?.limit_bytes ?? null;
  const used = formatBytes(locale, totals.bytes);
  const usage =
    limit === null
      ? t("summary.used", { used })
      : t("summary.usedOfLimit", { used, limit: formatBytes(locale, limit) });
  const cards = [
    {
      key: "files",
      title: t("summary.files"),
      icon: FileStack,
      value: format.number(totals.files),
      note: totals.failed > 0 ? t("summary.failedUsage", { failed: totals.failed, usage }) : usage,
    },
    {
      key: "chunks",
      title: t("summary.chunks"),
      icon: Boxes,
      value: format.number(totals.chunks),
      note: t("summary.inIndex"),
    },
    {
      key: "processing",
      title: t("summary.processing"),
      icon: Loader,
      value: format.number(totals.processing),
      note: totals.processing > 0 ? t("summary.busy") : t("summary.caughtUp"),
    },
    {
      key: "embeddings",
      title: t("summary.embeddings"),
      icon: Cpu,
      value: index ? t("summary.dimensions", { dimensions: index.index.dimensions }) : "—",
      // The model's name comes from the API and stays as written.
      note: index?.index.embedding_model ?? common("feedback.loading"),
    },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {cards.map((card) => (
        <Card key={card.key} className="shadow-xs">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 font-normal text-muted-foreground text-sm">
              <span className="grid size-7 place-items-center rounded-lg border bg-muted">
                <card.icon className="size-4" />
              </span>
              {card.title}
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1">
            <div className="text-2xl tabular-nums leading-none tracking-tight">{card.value}</div>
            <p className="truncate text-muted-foreground text-sm" title={card.note}>
              {card.note}
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
