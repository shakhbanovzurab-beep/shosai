"use client";

import { Layers, Search } from "lucide-react";
import { useTranslations } from "use-intl";

import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group";
import { Spinner } from "@/components/ui/spinner";

import type { Skill } from "../domain/contract";
import { useDirectorySearch } from "../model/use-directory-search";
import { SkillCandidates } from "./skill-candidates";

export function SkillsReadyMade({ installed }: { installed: Skill[] }) {
  const t = useTranslations("studioSkills");
  const { state, search } = useDirectorySearch();

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <InputGroup className="h-11">
          <InputGroupAddon>{state.status === "loading" ? <Spinner /> : <Search />}</InputGroupAddon>
          <InputGroupInput
            type="search"
            dir="auto"
            placeholder={t("readyMade.placeholder")}
            aria-label={t("readyMade.label")}
            aria-describedby="skills-search-help"
            onChange={(event) => search(event.currentTarget.value)}
          />
        </InputGroup>
        <p id="skills-search-help" className="text-muted-foreground text-xs">
          {t("readyMade.help")}
        </p>
      </div>
      {state.error ? (
        <p role="alert" className="text-destructive text-sm">
          {state.error}
        </p>
      ) : null}
      {state.status === "done" && !state.error && state.results.length === 0 ? (
        <p className="py-8 text-center text-muted-foreground text-sm">{t("readyMade.noMatches")}</p>
      ) : null}
      {state.results.length > 0 ? <SkillCandidates candidates={state.results} installed={installed} /> : null}
      {state.status === "idle" ? (
        <Empty className="py-6">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <Layers />
            </EmptyMedia>
            <EmptyTitle>{t("readyMade.emptyTitle")}</EmptyTitle>
            <EmptyDescription>{t("readyMade.emptyDescription")}</EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : null}
    </div>
  );
}
