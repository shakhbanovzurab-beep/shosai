"use client";

import type { ReactNode } from "react";

import { useTranslations } from "next-intl";
import { useDefaultLayout } from "react-resizable-panels";

import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";

const PANEL_IDS = ["support-tickets", "support-ticket"];

/**
 * Table and ticket panel side by side; drag the border to resize. The width is remembered in this browser.
 * The table keeps at least 450px.
 */
export function SupportSplit({ table, panel }: { table: ReactNode; panel: ReactNode }) {
  const t = useTranslations("pagesSupport");
  const { defaultLayout, onLayoutChanged } = useDefaultLayout({ id: "support-split", panelIds: PANEL_IDS });

  return (
    <ResizablePanelGroup
      orientation="horizontal"
      defaultLayout={defaultLayout}
      onLayoutChanged={onLayoutChanged}
      className="min-h-0"
    >
      <ResizablePanel id={PANEL_IDS[0]} minSize={450} className="min-h-0">
        {table}
      </ResizablePanel>
      {panel ? (
        <>
          <ResizableHandle withHandle />
          <ResizablePanel id={PANEL_IDS[1]} defaultSize="36%" minSize={360} maxSize="65%" className="min-h-0">
            <aside aria-label={t("panel.ticket")} className="h-full bg-background">
              {panel}
            </aside>
          </ResizablePanel>
        </>
      ) : null}
    </ResizablePanelGroup>
  );
}
