import { recentLeadsData } from "../../data/crm-v1/recent-leads";
import { InsightCards } from "./insight-cards";
import { OperationalCards } from "./operational-cards";
import { OverviewCards } from "./overview-cards";
import { RecentLeadsTable } from "./recent-leads-table";

export function CrmV1Tab() {
  return (
    <div className="flex flex-col gap-4 md:gap-6">
      <OverviewCards />
      <InsightCards />
      <OperationalCards />
      <RecentLeadsTable data={recentLeadsData} />
    </div>
  );
}
