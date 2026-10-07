import type { DashboardTab } from "../domain/dashboard-tabs";
import { AnalyticsTab } from "./analytics/analytics-tab";
import { CrmTab } from "./crm/crm-tab";
import { CrmV1Tab } from "./crm-v1/crm-v1-tab";
import { DashboardTabs } from "./dashboard-tabs";

export function DashboardScreen({ tab }: { tab: DashboardTab }) {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-3xl tracking-tight">Дашборд</h1>
      <DashboardTabs value={tab} panels={{ analytics: <AnalyticsTab />, crm: <CrmTab />, "crm-v1": <CrmV1Tab /> }} />
    </div>
  );
}
