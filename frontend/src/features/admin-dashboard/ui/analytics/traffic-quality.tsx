"use client";

import dynamic from "next/dynamic";

import { Ellipsis } from "lucide-react";

import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const TrafficQualityChart = dynamic(
  () => import("./traffic-quality-chart").then((chartModule) => chartModule.TrafficQualityChart),
  { loading: () => <Skeleton className="h-68 w-full" /> },
);

export function TrafficQuality() {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="font-normal">Качество трафика</CardTitle>
        <CardAction>
          <Ellipsis className="size-4" />
        </CardAction>
      </CardHeader>

      <CardContent>
        <TrafficQualityChart />
      </CardContent>
    </Card>
  );
}
