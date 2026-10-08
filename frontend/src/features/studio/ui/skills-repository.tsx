"use client";

import { useActionState } from "react";

import { Link2, Search } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";

import type { Skill } from "../domain/contract";
import { type ScanState, scanRepository } from "../model/skill-actions";
import { SkillCandidates } from "./skill-candidates";

/** Your own skills: point at a public GitHub repository and pick from the SKILL.md files in it. */
export function SkillsRepository({ installed }: { installed: Skill[] }) {
  const t = useTranslations("studioSkills");
  const [state, scan, scanning] = useActionState((_previous: ScanState, form: FormData) => scanRepository(form, t), {
    results: null,
    error: null,
  });

  return (
    <div className="flex flex-col gap-4">
      <form action={scan} className="flex flex-col gap-2">
        <Label htmlFor="skills-repo" className="font-medium text-muted-foreground text-xs uppercase tracking-wide">
          {t("repository.label")}
        </Label>
        <div className="flex gap-2">
          <Input
            id="skills-repo"
            name="repository"
            required
            dir="auto"
            placeholder={t("repository.placeholder")}
            aria-describedby="skills-repo-help"
            className="h-11"
          />
          <Button type="submit" size="lg" className="h-11" disabled={scanning}>
            {scanning ? <Spinner data-icon="inline-start" /> : <Search data-icon="inline-start" />}
            {t("repository.find")}
          </Button>
        </div>
        <p id="skills-repo-help" className="text-muted-foreground text-xs">
          {t("repository.help")}
        </p>
      </form>
      {state.error ? (
        <p role="alert" className="text-destructive text-sm">
          {state.error}
        </p>
      ) : null}
      {state.results ? <SkillCandidates candidates={state.results} installed={installed} /> : null}
      {state.results === null && !state.error ? (
        <Empty className="py-6">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <Link2 />
            </EmptyMedia>
            <EmptyTitle>{t("repository.emptyTitle")}</EmptyTitle>
            <EmptyDescription>{t("repository.emptyDescription")}</EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : null}
    </div>
  );
}
