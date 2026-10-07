"use client";

import { useTranslations } from "next-intl";

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

import type { Team } from "../../domain/contract";
import { type LibraryQuery, MEETING_SCOPES } from "../../domain/library";
import { SearchField, TeamFilter } from "../shared/filters";

/** Search, team and (for meetings) whether to show only the ones you took part in. */
export function LibraryToolbar({
  query,
  teams,
  onChange,
  searchLabel,
  withScope = false,
}: {
  query: LibraryQuery;
  teams: Team[];
  onChange: (query: LibraryQuery) => void;
  searchLabel: string;
  withScope?: boolean;
}) {
  const t = useTranslations("workspaceMeetings.scope");
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
      <SearchField
        value={query.q}
        onChange={(q) => onChange({ ...query, q })}
        placeholder={searchLabel}
        label={searchLabel}
      />
      <TeamFilter teams={teams} value={query.team} onChange={(team) => onChange({ ...query, team })} />
      {withScope ? (
        <ToggleGroup
          type="single"
          variant="outline"
          spacing={0}
          value={query.scope}
          onValueChange={(value) => {
            const scope = MEETING_SCOPES.find((s) => s === value);
            if (scope) onChange({ ...query, scope });
          }}
          aria-label={t("label")}
          className="sm:ms-auto"
        >
          {MEETING_SCOPES.map((scope) => (
            <ToggleGroupItem key={scope} value={scope} className="px-3">
              {t(scope)}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      ) : null}
    </div>
  );
}
