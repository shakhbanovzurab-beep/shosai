"use client";

import type * as React from "react";

import { useRouter } from "next/navigation";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { DASHBOARD_TABS, type DashboardTab } from "../domain/dashboard-tabs";

const DASHBOARD_PATH = "/admin/dashboard";

interface DashboardTabsProps {
  readonly value: DashboardTab;
  /** The content of every tab, rendered on the server. */
  readonly panels: Record<DashboardTab, React.ReactNode>;
}

/** The dashboard's tabs, kept in the URL (`?tab=crm`) so a tab can be linked to and survives a reload. */
export function DashboardTabs({ value, panels }: DashboardTabsProps) {
  const router = useRouter();

  return (
    <Tabs
      value={value}
      onValueChange={(next) => {
        const tab = DASHBOARD_TABS.find((t) => t.id === next);
        if (tab)
          router.replace(tab.id === "analytics" ? DASHBOARD_PATH : `${DASHBOARD_PATH}?tab=${tab.id}`, {
            scroll: false,
          });
      }}
      className="flex flex-col gap-6"
    >
      <TabsList variant="line" className="w-full justify-start border-b">
        {DASHBOARD_TABS.map((tab) => (
          <TabsTrigger key={tab.id} value={tab.id} className="flex-none px-3">
            {tab.label}
          </TabsTrigger>
        ))}
      </TabsList>
      {DASHBOARD_TABS.map((tab) => (
        <TabsContent key={tab.id} value={tab.id}>
          {panels[tab.id]}
        </TabsContent>
      ))}
    </Tabs>
  );
}
