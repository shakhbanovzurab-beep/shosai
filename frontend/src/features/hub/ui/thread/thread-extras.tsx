import type { ReactNode } from "react";

import { useTranslations } from "use-intl";

import { Link } from "@/lib/navigation";

import type { ThreadDetail, ThreadLinkKind } from "../../domain/contract-threads";
import { threadPath } from "../../domain/paths";
import { useHubPhrases } from "../shared/phrases";
import { GapIcon } from "../shared/urgency";
import { SourceCard } from "../why/source-card";

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="flex flex-col gap-3">
      <h3 id={id} className="font-medium text-muted-foreground text-sm">
        {title}
      </h3>
      {children}
    </section>
  );
}

const LINK_ORDER: ThreadLinkKind[] = ["causes", "blocked_by", "outcome_of"];

/** What this holds up, what holds it up, and what follows from its decision. */
export function Links({ detail, onOpen }: { detail: ThreadDetail; onOpen: (threadId: string) => void }) {
  const t = useTranslations("hubDetail");
  const say = useHubPhrases();
  if (detail.links.length === 0) return null;
  return (
    <div className="flex flex-col gap-5">
      {LINK_ORDER.map((kind) => {
        const linked = detail.links.filter((l) => l.kind === kind);
        if (linked.length === 0) return null;
        return (
          <Section key={kind} id={`thread-links-${kind}`} title={t(`thread.links.${kind}`)}>
            <ul className="flex flex-col gap-2">
              {linked.map(({ thread }) => (
                <li key={thread.id} className="flex flex-col">
                  <Link
                    href={threadPath(thread.hubId, thread.id)}
                    scroll={false}
                    dir="auto"
                    className="w-fit text-sm underline decoration-border underline-offset-4 hover:decoration-foreground"
                    onClick={(event) => {
                      if (event.metaKey || event.ctrlKey || event.shiftKey) return;
                      event.preventDefault();
                      onOpen(thread.id);
                    }}
                  >
                    {thread.subject}
                  </Link>
                  <span className="flex items-center gap-1.5 text-muted-foreground text-xs">
                    {thread.gap ? <GapIcon kind={thread.gap.kind} className="size-3" /> : null}
                    {say.status(thread)}
                  </span>
                </li>
              ))}
            </ul>
          </Section>
        );
      })}
    </div>
  );
}

/** Every mention: meeting, who said it, the moment and the words. */
export function Sources({ detail }: { detail: ThreadDetail }) {
  const t = useTranslations("hubDetail");
  if (detail.sources.length === 0) return null;
  return (
    <Section id="thread-sources" title={t("thread.sources")}>
      <ul className="flex flex-col gap-4">
        {detail.sources.map((source) => (
          <li key={`${source.sessionId}-${source.startMs}`} className="border-t pt-4 first:border-t-0 first:pt-0">
            <SourceCard evidence={source} />
          </li>
        ))}
      </ul>
    </Section>
  );
}

/** Who dismissed a gap, when, and until when; or that the time ran out and it came back. */
export function Dismissals({ detail }: { detail: ThreadDetail }) {
  const t = useTranslations("hubDetail");
  const say = useHubPhrases();
  const refutation = detail.refutation;
  if (!refutation) return null;
  const who =
    refutation.by === "human" ? t("thread.dismissedByYou") : t("thread.disproved", { evidence: refutation.evidence });
  return (
    <Section id="thread-dismissals" title={t("thread.dismissals")}>
      <p className="text-sm">
        {who} · {say.date(refutation.at)}
        {refutation.until ? (
          <span className="text-muted-foreground">
            {" · "}
            {t("thread.dismissedUntil", { date: say.date(refutation.until) })}
          </span>
        ) : null}
      </p>
      {refutation.returned ? <p className="text-muted-foreground text-xs">{t("thread.returned")}</p> : null}
    </Section>
  );
}
