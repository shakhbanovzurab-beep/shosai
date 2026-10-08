"use client";

import { useTranslations } from "use-intl";

import { Link } from "@/lib/navigation";

import { openFor } from "../../domain/tasks";
import { useDecisions, useMeetings, useResources, useTasks, useWorkspace } from "../../model/use-workspace";
import { BlockState } from "../shared/block-state";
import { QuietEmpty, TeamSection } from "../shared/layout";
import { TaskList } from "../tasks/task-groups";
import { ComingUp } from "./coming-up";
import { ActiveProjects, RecentDecisions } from "./home-lists";

const MORE = "text-muted-foreground text-sm underline-offset-4 hover:text-foreground hover:underline";

/** Two rows on wide screens (now: needs you, coming up; then: projects, decisions); one column on phones. */
export function HomeBlocks({ now }: { now: number }) {
  const t = useTranslations("workspaceHome");
  const { ws, slug, state, path } = useWorkspace();
  const resources = useResources();
  const tasks = useTasks();
  const meetings = useMeetings();
  const decisions = useDecisions();
  const ctx = {
    ws,
    slug,
    now,
    meId: state.me_id,
    members: state.members,
    teams: state.teams,
    projects: state.projects,
  };

  return (
    <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
      <TeamSection
        id="needs-you"
        title={t("blocks.needsYou")}
        action={
          <Link href={path("/tasks")} className={MORE}>
            {t("blocks.allTasks")}
          </Link>
        }
      >
        <BlockState state={tasks} what="yourTasks" onRetry={() => void resources.tasks.refresh()}>
          {(data) => {
            const mine = openFor(data.tasks, state.me_id, now);
            if (mine.length === 0) return <QuietEmpty>{t("blocks.nothingWaiting")}</QuietEmpty>;
            return (
              <div className="flex flex-col gap-2">
                <TaskList items={mine.slice(0, 5)} showOwner={false} {...ctx} />
                {mine.length > 5 ? (
                  <Link href={path("/tasks")} className={MORE}>
                    {t("blocks.moreTasks", { count: mine.length - 5 })}
                  </Link>
                ) : null}
              </div>
            );
          }}
        </BlockState>
      </TeamSection>
      <TeamSection id="coming-up" title={t("blocks.comingUp")}>
        <BlockState
          state={meetings}
          what="upcomingMeetings"
          height="h-32"
          onRetry={() => void resources.meetings.refresh()}
        >
          {(data) => <ComingUp upcoming={data.upcoming} state={state} now={now} />}
        </BlockState>
      </TeamSection>
      <TeamSection
        id="active-projects"
        title={t("blocks.projects")}
        action={
          <Link href={path("/projects")} className={MORE}>
            {t("blocks.allProjects")}
          </Link>
        }
      >
        <BlockState state={tasks} what="projects" onRetry={() => void resources.tasks.refresh()}>
          {(data) => (
            <ActiveProjects projects={state.projects} tasks={data.tasks} state={state} slug={slug} now={now} />
          )}
        </BlockState>
      </TeamSection>
      <TeamSection
        id="recent-decisions"
        title={t("blocks.recentDecisions")}
        action={
          <Link href={path("/decisions")} className={MORE}>
            {t("blocks.decisionLog")}
          </Link>
        }
      >
        <BlockState state={decisions} what="decisions" onRetry={() => void resources.decisions.refresh()}>
          {(data) => <RecentDecisions decisions={data.decisions} slug={slug} now={now} />}
        </BlockState>
      </TeamSection>
    </div>
  );
}
