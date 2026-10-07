"use client";

import dynamic from "next/dynamic";

import { Ellipsis } from "lucide-react";

import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { campaignsData, referrersData, sourcesData } from "../../data/analytics/traffic-sources";

const TrafficSourceBarChart = dynamic(
  () => import("./traffic-source-bar-chart").then((chartModule) => chartModule.TrafficSourceBarChart),
  { loading: () => <Skeleton className="h-64 w-full" /> },
);

export function TopTrafficSources() {
  return (
    <Card className="h-full gap-2">
      <CardHeader>
        <CardTitle className="font-normal">Источники трафика</CardTitle>
        <CardAction>
          <Ellipsis className="size-4" />
        </CardAction>
      </CardHeader>

      <CardContent className="px-0">
        <Tabs defaultValue="sources" className="flex flex-col gap-3">
          <TabsList className="w-full justify-start border-b px-2.5" variant="line">
            <TabsTrigger className="flex-none font-normal" value="sources">
              Источники
            </TabsTrigger>
            <TabsTrigger className="flex-none font-normal" value="campaigns">
              Кампании
            </TabsTrigger>
            <TabsTrigger className="flex-none font-normal" value="referrers">
              Рефереры
            </TabsTrigger>
          </TabsList>

          <TabsContent value="sources" className="px-4">
            <TrafficSourceBarChart data={sourcesData} />
          </TabsContent>

          <TabsContent value="campaigns" className="px-4">
            <TrafficSourceBarChart data={campaignsData} />
          </TabsContent>
          <TabsContent value="referrers" className="px-4">
            <TrafficSourceBarChart data={referrersData} />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
