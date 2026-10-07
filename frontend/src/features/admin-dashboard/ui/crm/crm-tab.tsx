import { KpiCards } from "./kpi-cards";
import { OpportunitiesSection } from "./opportunities-section";
import { PipelineActivity } from "./pipeline-activity";
import { TaskReminders } from "./task-reminders";

export function CrmTab() {
  return (
    <div className="flex flex-col gap-4 md:gap-6">
      <KpiCards />
      <PipelineActivity />
      <TaskReminders />
      <OpportunitiesSection />
    </div>
  );
}
