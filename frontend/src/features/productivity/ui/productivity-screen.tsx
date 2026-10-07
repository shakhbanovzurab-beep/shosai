import { getTranslations } from "next-intl/server";

import { viewer } from "../data/viewer";
import { CalendarPanel } from "./calendar-panel";
import { FocusCard } from "./focus-card";
import { Greeting } from "./greeting";
import { ProjectsSection } from "./projects-section";
import { RecentNotesCard } from "./recent-notes-card";
import { ContributionSkyline } from "./skyline/contribution-skyline";
import { TasksSection } from "./tasks-section";

/** The user panel home: the day's work at the start; calendar, focus timer and recent notes at the end. */
export async function ProductivityScreen() {
  const t = await getTranslations("productivity");
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
      <div className="flex min-w-0 flex-col gap-6 lg:col-span-9">
        <Greeting name={viewer.firstName} />
        <ContributionSkyline />
        <TasksSection />
        <ProjectsSection />
      </div>

      <aside aria-label={t("sidePanel")} className="flex min-w-0 flex-col gap-6 lg:col-span-3">
        <CalendarPanel />
        <FocusCard />
        <RecentNotesCard />
      </aside>
    </div>
  );
}
