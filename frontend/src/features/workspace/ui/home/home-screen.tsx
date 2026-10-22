"use client";

import type { ReactNode } from "react";

import { UserPlus } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { useNow } from "@/hooks/use-now";

import { isQuietStart, setupSteps } from "../../domain/setup";
import { openInviteDialog } from "../../model/invite-dialog-store";
import { useDecisions, useKnowledge, useMeetings, useTasks, useWorkspace } from "../../model/use-workspace";
import { QuietEmpty, TeamPage, TeamPageHeader } from "../shared/layout";
import { HomeBlocks } from "./home-blocks";
import { SetupChecklist } from "./setup-checklist";

/**
 * The workspace's home answers three questions: what needs me, what's next, and where the work stands.
 * `children` are other slices' quiet notes, shown under the header.
 */
export function TeamHomeScreen({ children }: { children?: ReactNode }) {
  const t = useTranslations("workspaceHome");
  const { state, can } = useWorkspace();
  const tasks = useTasks();
  const meetings = useMeetings();
  const decisions = useDecisions();
  const knowledge = useKnowledge();
  const now = useNow();
  if (now === null) return null;

  const steps =
    can.admin && meetings.status === "ready" && knowledge.status === "ready"
      ? setupSteps(state, meetings.data.meetings, knowledge.data.items)
      : null;
  const quiet =
    meetings.status === "ready" &&
    decisions.status === "ready" &&
    tasks.status === "ready" &&
    isQuietStart(
      meetings.data.meetings,
      meetings.data.upcoming,
      decisions.data.decisions,
      tasks.data.tasks,
      state.projects.length,
    );

  return (
    <TeamPage>
      <TeamPageHeader
        title={<span dir="auto">{state.workspace.name}</span>}
        description={t("description")}
        actions={
          can.invite ? (
            <Button variant="outline" onClick={openInviteDialog}>
              <UserPlus data-icon="inline-start" />
              {t("invitePeople")}
            </Button>
          ) : null
        }
      />
      {children}
      {steps ? <SetupChecklist steps={steps} /> : null}
      {quiet ? <QuietEmpty>{t("quietStart")}</QuietEmpty> : <HomeBlocks now={now} />}
    </TeamPage>
  );
}
