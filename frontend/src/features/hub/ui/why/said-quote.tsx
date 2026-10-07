import Link from "next/link";

import { Play } from "lucide-react";
import { useTranslations } from "next-intl";

import type { Evidence } from "../../domain/contract";
import { meetingPath } from "../../domain/paths";
import { momentLabel } from "../../domain/phrases";
import { useHubPhrases } from "../shared/phrases";

/**
 * Words as said, with who said them and a way to that moment of the recording, for places where the
 * meeting is already named next to it. No speaker, no name; no moment, no link.
 */
export function SaidQuote({ evidence }: { evidence: Evidence }) {
  const t = useTranslations("hubDetail");
  const say = useHubPhrases();
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <blockquote className="text-pretty border-border border-s-2 ps-2.5 text-sm">
        <span dir="auto">{say.quote(evidence.quote)}</span>
        {evidence.speaker ? (
          <span className="text-muted-foreground">
            {" — "}
            <span dir="auto">{evidence.speaker}</span>
          </span>
        ) : null}
      </blockquote>
      {evidence.startMs === null ? null : (
        <Link
          href={meetingPath(evidence.sessionId, evidence.startMs)}
          className="inline-flex w-fit items-center gap-1 text-muted-foreground text-xs underline-offset-4 hover:text-foreground hover:underline"
        >
          <Play className="size-3" aria-hidden="true" />
          {t("why.jump")} · <span className="font-mono tabular-nums">{momentLabel(evidence.startMs)}</span>
        </Link>
      )}
    </div>
  );
}
