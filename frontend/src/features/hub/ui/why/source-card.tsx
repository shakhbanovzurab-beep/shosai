import Link from "next/link";

import { Play } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";

import type { Evidence } from "../../domain/contract";
import { meetingPath } from "../../domain/paths";
import { momentLabel } from "../../domain/phrases";
import { useHubPhrases } from "../shared/phrases";

/*
 * Where a statement comes from: the meeting, who said it, the moment and the words. Unknown stays
 * unknown: no speaker, no "Said by" line; no moment, no link to it.
 */

function Row({ term, children }: { term: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[5.5rem_minmax(0,1fr)] items-baseline gap-2">
      <dt className="text-muted-foreground text-xs">{term}</dt>
      <dd className="min-w-0 text-sm">{children}</dd>
    </div>
  );
}

export function SourceCard({ evidence }: { evidence: Evidence }) {
  const t = useTranslations("hubDetail");
  const say = useHubPhrases();
  const date = say.date(evidence.meetingStartedAt);
  return (
    <div className="flex flex-col gap-2.5">
      <dl className="flex flex-col gap-1.5">
        <Row term={t("why.source")}>
          <Link
            href={meetingPath(evidence.sessionId)}
            className="underline decoration-border underline-offset-4 hover:decoration-foreground"
          >
            {t("why.meeting", { date, title: evidence.meetingTitle })}
          </Link>
        </Row>
        {evidence.speaker ? (
          <Row term={t("why.said")}>
            <span dir="auto">{evidence.speaker}</span>
          </Row>
        ) : null}
        {evidence.startMs === null ? null : (
          <Row term={t("why.moment")}>
            <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="font-mono text-xs tabular-nums">{momentLabel(evidence.startMs)}</span>
              <Button asChild variant="outline" size="xs" className="bg-background">
                <Link href={meetingPath(evidence.sessionId, evidence.startMs)}>
                  <Play data-icon="inline-start" aria-hidden="true" />
                  {t("why.jump")}
                </Link>
              </Button>
            </span>
          </Row>
        )}
      </dl>
      <blockquote dir="auto" className="text-pretty border-border border-s-2 ps-3 text-sm leading-relaxed">
        {say.quote(evidence.quote)}
      </blockquote>
    </div>
  );
}
