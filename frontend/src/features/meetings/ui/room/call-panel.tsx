import type { ReactNode } from "react";

import { X } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { useDirection } from "@/components/ui/direction";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useIsLg } from "@/hooks/use-lg";

export type CallPanelKind = "chat" | "people";

type CallPanelProps = {
  panel: CallPanelKind | null;
  onPanel: (panel: CallPanelKind | null) => void;
  chat: ReactNode;
  people: ReactNode;
};

/** Чат и участники: колонкой рядом со сценой на широком экране, шторкой — на узком. */
export function CallPanel({ panel, onPanel, chat, people }: CallPanelProps) {
  const t = useTranslations("meetingRoom");
  const wide = useIsLg();
  const direction = useDirection();
  if (panel === null) return null;
  const tabs = (
    <Tabs
      value={panel}
      onValueChange={(value) => onPanel(value === "people" ? "people" : "chat")}
      className="min-h-0 flex-1"
    >
      <TabsList className="w-full">
        <TabsTrigger value="chat">{t("panel.chat")}</TabsTrigger>
        <TabsTrigger value="people">{t("panel.people")}</TabsTrigger>
      </TabsList>
      <TabsContent value="chat" className="flex min-h-0 flex-col">
        {chat}
      </TabsContent>
      <TabsContent value="people" className="flex min-h-0 flex-col">
        {people}
      </TabsContent>
    </Tabs>
  );
  if (!wide)
    return (
      <Sheet open onOpenChange={(open) => (open ? undefined : onPanel(null))}>
        <SheetContent side={direction === "rtl" ? "left" : "right"} className="w-full gap-0 p-4 sm:max-w-sm">
          {/* Вкладки уже называют панель; заголовок шторки — для экранного чтеца. */}
          <SheetHeader className="sr-only">
            <SheetTitle>{t(`panel.${panel}`)}</SheetTitle>
          </SheetHeader>
          {tabs}
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
      {tabs}
    </aside>
  );
}
