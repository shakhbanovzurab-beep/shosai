"use client";

import { useState } from "react";

import { Plus, UsersRound } from "lucide-react";
import { useTranslations } from "use-intl";

import { ConfirmDestructive } from "@/components/feedback";
import { Button } from "@/components/ui/button";

import type { Team } from "../../domain/contract";
import { visibleTeams } from "../../domain/people";
import { deleteTeam } from "../../model/group-actions";
import { useWorkspace } from "../../model/use-workspace";
import { EmptyMessage } from "../shared/empty-message";
import { TeamCard } from "./team-card";
import { TeamDialog } from "./team-dialog";

/** Teams group people for sharing; optional, so a small workspace can ignore them entirely. */
export function TeamsTab() {
  const t = useTranslations("workspaceMembers");
  const { ws, state, can } = useWorkspace();
  const [editing, setEditing] = useState<{ team: Team | null } | null>(null);
  const [deleting, setDeleting] = useState<Team | null>(null);
  const teams = visibleTeams(state, can.me, can.admin);
  const newTeam = can.manageTeams ? (
    <Button variant="outline" onClick={() => setEditing({ team: null })}>
      <Plus data-icon="inline-start" />
      {t("teams.new")}
    </Button>
  ) : null;

  return (
    <div className="flex flex-col gap-4">
      {teams.length === 0 ? (
        <EmptyMessage icon={UsersRound} title={t("teams.empty")} text={t("teams.emptyHint")} action={newTeam} />
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-muted-foreground text-sm">{t("teams.intro")}</p>
            {newTeam}
          </div>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {teams.map((team) => (
              <TeamCard
                key={team.id}
                ws={ws}
                team={team}
                state={state}
                canManage={can.manageTeams}
                onEdit={() => setEditing({ team })}
                onDelete={() => setDeleting(team)}
              />
            ))}
          </div>
        </>
      )}
      <TeamDialog
        team={editing?.team ?? null}
        open={editing !== null}
        onOpenChange={(open) => (open ? undefined : setEditing(null))}
      />
      <ConfirmDestructive
        open={deleting !== null}
        title={t("teams.deleteTitle", { name: deleting?.name ?? "" })}
        description={t("teams.deleteDescription")}
        confirmLabel={t("team.delete")}
        onConfirm={() => {
          const team = deleting;
          setDeleting(null);
          if (team) void deleteTeam(ws, team, t);
        }}
        onCancel={() => setDeleting(null)}
      />
    </div>
  );
}
