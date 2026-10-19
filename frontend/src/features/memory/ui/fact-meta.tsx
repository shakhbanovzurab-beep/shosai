"use client";

import { useFormatter, useTranslations } from "use-intl";

import type { MemoryFact } from "../domain/contract";

/** «Из чата · 12 окт.»: у каждого факта виден источник (ADR 0030) и когда он появился. */
export function FactMeta({ fact }: { fact: MemoryFact }) {
  const t = useTranslations("memory");
  const format = useFormatter();
  const { kind, title } = fact.source;
  let source = t(`source.${kind}`);
  if (kind === "meeting" && title) source = t("source.meetingNamed", { title });
  return (
    <span className="min-w-0">
      {t("meta", { source, date: format.dateTime(new Date(fact.created_at), { month: "short", day: "numeric" }) })}
    </span>
  );
}
