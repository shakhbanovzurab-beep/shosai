import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { AnalyticsKpiStrip } from "./analytics-kpi-strip";
import { AnalyticsToolbar } from "./analytics-toolbar";
import { RealtimeVisitors } from "./realtime-visitors";
import { TopPages } from "./top-pages";
import { TopTrafficSources } from "./top-traffic-sources";
import { TrafficQuality } from "./traffic-quality";

// Import this stylesheet in any page or component that renders country flag classes.
import "@/styles/flag-icons/flags.css";

const COMING_SOON = [
  { value: "audience", label: "Аудитория" },
  { value: "acquisition", label: "Привлечение" },
  { value: "engagement", label: "Вовлечённость" },
  { value: "conversions", label: "Конверсии" },
] as const;

export function AnalyticsTab() {
  return (
    <Tabs defaultValue="overview" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <TabsList className="gap-1">
          <TabsTrigger value="overview">Обзор</TabsTrigger>
          {COMING_SOON.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value}>
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
        <AnalyticsToolbar />
      </div>

      <TabsContent value="overview" className="flex flex-col gap-4">
        <AnalyticsKpiStrip />
        <div className="grid grid-cols-1 items-stretch gap-4 xl:grid-cols-12">
          <div className="xl:col-span-7">
            <TrafficQuality />
          </div>
          <div className="xl:col-span-5">
            <RealtimeVisitors />
          </div>
        </div>
        <div className="grid grid-cols-1 items-stretch gap-4 xl:grid-cols-12">
          <div className="xl:col-span-7">
            <TopPages />
          </div>
          <div className="xl:col-span-5 xl:col-start-8">
            <TopTrafficSources />
          </div>
        </div>
      </TabsContent>

      {COMING_SOON.map((tab) => (
        <TabsContent key={tab.value} value={tab.value}>
          <div className="flex h-64 items-center justify-center rounded-xl border border-border border-dashed text-muted-foreground">
            Раздел «{tab.label}» скоро появится.
          </div>
        </TabsContent>
      ))}
    </Tabs>
  );
}
