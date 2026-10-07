"use client";

import { useTransition } from "react";

import { Check, ExternalLink, Plus } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

import type { Skill, SkillCandidate } from "../domain/contract";
import { sameSkill } from "../domain/skills";
import { installSkill } from "../model/skill-actions";

function CandidateRow({ candidate, installed }: { candidate: SkillCandidate; installed: boolean }) {
  const t = useTranslations("studioSkills");
  const tc = useTranslations("common");
  const [pending, startTransition] = useTransition();

  const install = () =>
    startTransition(async () => {
      await installSkill(candidate, t);
    });

  return (
    <li className="flex items-start gap-3 rounded-xl border p-4">
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <span dir="auto" className="truncate font-medium font-mono text-sm">
          {candidate.name}
        </span>
        <a
          href={candidate.source_url}
          target="_blank"
          rel="noreferrer"
          className="flex w-fit items-center gap-1 truncate text-muted-foreground text-xs hover:text-foreground"
        >
          <span dir="auto" className="min-w-0 truncate">
            {candidate.reference}
          </span>
          <ExternalLink className="size-3 shrink-0 rtl:-scale-x-100" aria-hidden="true" />
        </a>
        {candidate.description ? (
          <p dir="auto" className="line-clamp-2 text-muted-foreground text-sm">
            {candidate.description}
          </p>
        ) : null}
      </div>
      {candidate.installs !== null ? (
        <span className="shrink-0 pt-1 text-muted-foreground text-xs tabular-nums">
          {t("candidate.installs", { count: candidate.installs })}
        </span>
      ) : null}
      <Button size="sm" variant={installed ? "ghost" : "outline"} disabled={installed || pending} onClick={install}>
        {pending ? <Spinner data-icon="inline-start" /> : null}
        {!pending && installed ? <Check data-icon="inline-start" /> : null}
        {!pending && !installed ? <Plus data-icon="inline-start" /> : null}
        {installed ? t("candidate.installed") : tc("actions.add")}
      </Button>
    </li>
  );
}

/** Search or scan results, each with an Add button (or "Installed"). */
export function SkillCandidates({ candidates, installed }: { candidates: SkillCandidate[]; installed: Skill[] }) {
  return (
    <ul className="flex flex-col gap-2">
      {candidates.map((candidate) => (
        <CandidateRow
          key={candidate.reference}
          candidate={candidate}
          installed={installed.some((skill) => sameSkill(candidate.reference, skill.reference))}
        />
      ))}
    </ul>
  );
}
