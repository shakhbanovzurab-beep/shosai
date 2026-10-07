"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { PlansTab } from "./plans-tab";
import { PromoTab } from "./promo-tab";

export function PlansScreen() {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl tracking-tight">Тарифы и промокоды</h1>
        <p className="text-muted-foreground text-sm">
          Цены и лимиты тарифов Leo, скидочные коды и то, к каким тарифам они применяются.
        </p>
      </div>

      <Tabs className="gap-4" defaultValue="plans">
        <TabsList
          variant="line"
          className="w-full justify-start gap-2 border-b ps-0 *:data-[slot=tabs-trigger]:flex-none"
        >
          <TabsTrigger value="plans">Тарифы</TabsTrigger>
          <TabsTrigger value="promo-codes">Промокоды</TabsTrigger>
        </TabsList>
        <TabsContent value="plans">
          <PlansTab />
        </TabsContent>
        <TabsContent value="promo-codes">
          <PromoTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
