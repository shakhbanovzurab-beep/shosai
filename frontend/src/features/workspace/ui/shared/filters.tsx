"use client";

import { Search, X } from "lucide-react";
import { useTranslations } from "next-intl";

import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from "@/components/ui/input-group";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

import type { Project, Team } from "../../domain/contract";
import { TeamDot } from "./badges";

const ALL = "all";

/** "All teams" or one team; the value is null for all. */
export function TeamFilter({
  teams,
  value,
  onChange,
  label,
}: {
  teams: Team[];
  value: string | null;
  onChange: (teamId: string | null) => void;
  label?: string;
}) {
  const t = useTranslations("workspace");
  if (teams.length === 0) return null;
  return (
    <Select value={value ?? ALL} onValueChange={(next) => onChange(next === ALL ? null : next)}>
      <SelectTrigger aria-label={label ?? t("filters.team")} className="w-full sm:w-44">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          <SelectItem value={ALL}>{t("filters.allTeams")}</SelectItem>
          {teams.map((team) => (
            <SelectItem key={team.id} value={team.id}>
              <TeamDot team={team} />
              <span dir="auto">{team.name}</span>
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  );
}

/** "All projects" or one project; the value is null for all. Hidden while there are none. */
export function ProjectFilter({
  projects,
  value,
  onChange,
}: {
  projects: Project[];
  value: string | null;
  onChange: (projectId: string | null) => void;
}) {
  const t = useTranslations("workspace");
  if (projects.length === 0) return null;
  return (
    <Select value={value ?? ALL} onValueChange={(next) => onChange(next === ALL ? null : next)}>
      <SelectTrigger aria-label={t("filters.project")} className="w-full sm:w-48">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          <SelectItem value={ALL}>{t("filters.allProjects")}</SelectItem>
          {projects.map((project) => (
            <SelectItem key={project.id} value={project.id}>
              <span dir="auto">{project.name}</span>
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  );
}

/** A search box with a clear button once something is typed. */
export function SearchField({
  value,
  onChange,
  placeholder,
  label,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  label: string;
}) {
  const t = useTranslations("workspace");
  return (
    <InputGroup className="w-full sm:max-w-72">
      <InputGroupAddon>
        <Search aria-hidden="true" />
      </InputGroupAddon>
      <InputGroupInput
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        aria-label={label}
        autoComplete="off"
        dir="auto"
        spellCheck={false}
      />
      {value ? (
        <InputGroupAddon align="inline-end">
          <InputGroupButton size="icon-xs" aria-label={t("filters.clearSearch")} onClick={() => onChange("")}>
            <X />
          </InputGroupButton>
        </InputGroupAddon>
      ) : null}
    </InputGroup>
  );
}
