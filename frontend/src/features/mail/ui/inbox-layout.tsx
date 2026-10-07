import type { ReactNode } from "react";

import { SidebarProvider } from "@/components/ui/sidebar";

import { MailSidebar } from "./mail-sidebar";

/** The standalone inbox frame: the mail sidebar beside the routed content. */
export function InboxLayout({ children }: { children: ReactNode }) {
  return (
    <div className="relative h-full">
      <SidebarProvider className="h-full min-h-0">
        <MailSidebar />
        {/* min-w-0 lets wide content truncate instead of stretching the inbox past the screen. */}
        <div className="size-full min-w-0">{children}</div>
      </SidebarProvider>
    </div>
  );
}
