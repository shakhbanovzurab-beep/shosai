"use client";

import { Suspense, use } from "react";

import Link from "next/link";

import { Repeat } from "lucide-react";
import { useTranslations } from "next-intl";

import { threadPath } from "../../domain/paths";
import { claimSignal } from "../../model/signal";
import { useHubPhrases } from "../shared/phrases";

function Signal({ hubId }: { hubId: string }) {
  const signal = use(claimSignal(hubId));
  const t = useTranslations("hubMeetings");
  const common = useTranslations("common");
  const say = useHubPhrases();
  if (!signal) return null;
  return (
    <div className="flex items-start gap-2.5 rounded-lg border px-3 py-2.5 text-sm" role="note">
      <Repeat className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <p className="min-w-0 text-pretty">
        {t("brief.signal", { subject: signal.thread.subject, circles: signal.thread.circles })}{" "}
        {signal.blockers.length > 0 ? `${t("brief.blockers", { quotes: say.quotes(signal.blockers) })} ` : null}
        <Link href={threadPath(signal.hub.id, signal.thread.id)} className="font-medium underline underline-offset-4">
          {common("actions.open")}
        </Link>
      </p>
    </div>
  );
}

/**
 * The assistant's one signal in a hub: a topic discussed three times without a decision, and what
 * stood in the way each time. Shown before the first question; nothing at all when there is none.
 */
export function HubSignal({ hubId }: { hubId: string }) {
  return (
    <Suspense fallback={null}>
      <Signal hubId={hubId} />
    </Suspense>
  );
}
