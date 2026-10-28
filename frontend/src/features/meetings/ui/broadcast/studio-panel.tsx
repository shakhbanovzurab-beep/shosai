import type { ReactNode } from "react";

import { X } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { useDirection } from "@/components/ui/direction";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useIsLg } from "@/hooks/use-lg";

export type StudioPanelKind = "chat" | "hands" | "waiting" | "stage";

type StudioTab = { kind: StudioPanelKind; count: number; content: ReactNode };

type StudioPanelProps = {
  panel: StudioPanelKind | null;
  onPanel: (panel: StudioPanelKind | null) => void;
  tabs: StudioTab[];
};

/** Чат, руки, зал ожидания и сцена: колонкой рядом со сценой на широком экране, шторкой — на узком. */
export function StudioPanel({ panel, onPanel, tabs }: StudioPanelProps) {
  const t = useTranslations("meetingBroadcast");
  const wide = useIsLg();
  const direction = useDirection();
  if (panel === null) return null;
  const content = (
    <Tabs
      value={panel}
      onValueChange={(value) => onPanel(tabs.find((tab) => tab.kind === value)?.kind ?? "chat")}
      className="min-h-0 flex-1"
    >
      <TabsList className="w-full">
        {tabs.map((tab) => (
          <TabsTrigger key={tab.kind} value={tab.kind}>
            {t(`panel.${tab.kind}`)}
            {tab.count > 0 ? <span className="text-muted-foreground tabular-nums">{tab.count}</span> : null}
          </TabsTrigger>
        ))}
      </TabsList>
      {tabs.map((tab) => (
        <TabsContent key={tab.kind} value={tab.kind} className="flex min-h-0 flex-col">
          {tab.content}
        </TabsContent>
      ))}
    </Tabs>
  );
  if (!wide)
    return (
      <Sheet open onOpenChange={(open) => (open ? undefined : onPanel(null))}>
        <SheetContent side={direction === "rtl" ? "left" : "right"} className="w-full gap-0 p-4 pt-12 sm:max-w-sm">
          <SheetHeader className="sr-only">
            <SheetTitle>{t(`panel.${panel}`)}</SheetTitle>
          </SheetHeader>
          {content}
        </SheetContent>
      </Sheet>
    );
  return (
    <aside aria-label={t(`panel.${panel}`)} className="flex w-80 shrink-0 flex-col gap-3 rounded-xl border bg-card p-3">
      <div className="flex justify-end">
        <Button variant="ghost" size="icon-sm" aria-label={t("panel.close")} onClick={() => onPanel(null)}>
          <X aria-hidden="true" />
        </Button>
      </div>
      {content}
    </aside>
  );
}
