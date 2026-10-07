"use client";

import * as React from "react";

import { useTranslations } from "next-intl";

import { useDirection } from "@/components/ui/direction";
import { Drawer, DrawerContent, DrawerDescription, DrawerTitle } from "@/components/ui/drawer";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";
import { useSidebar } from "@/components/ui/sidebar";
import { setClientCookie } from "@/lib/cookie.client";

import type { Mail } from "../domain/mail";
import {
  DEFAULT_MAIL_LAYOUT,
  MAIL_DETAIL_PANEL_ID,
  MAIL_LAYOUT_COOKIE,
  MAIL_LIST_PANEL_ID,
} from "../domain/mail-layout";
import { useMailItems } from "../model/mail-store";
import { useMail } from "../model/use-mail";
import { InboxPane } from "./inbox-pane";
import { MailView } from "./mail-view";

interface MailProps {
  defaultLayout: readonly number[] | undefined;
}

const subscribeToNothing = () => () => undefined;
const getIsClient = (): boolean => true;
const getIsServer = (): boolean => false;

/** The full-height inbox screen: the message list and the reader, resizable on desktop, a drawer on mobile. */
export function MailInbox({ defaultLayout }: MailProps) {
  return (
    <div className="h-dvh min-h-0 overflow-hidden">
      <MailPanels defaultLayout={defaultLayout} />
    </div>
  );
}

/** The mailbox lives in a client store (model/mail-store), so menu actions update the list and the reader at once. */
function MailPanels({ defaultLayout }: MailProps) {
  const mails = useMailItems();
  const { isMobile } = useSidebar();
  const t = useTranslations("common");
  // The layout depends on the viewport, so render it only after hydration.
  const isClient = React.useSyncExternalStore(subscribeToNothing, getIsClient, getIsServer);

  if (!isClient) {
    return (
      <div className="flex size-full items-center justify-center text-muted-foreground text-sm" role="status">
        {t("feedback.loading")}
      </div>
    );
  }

  return isMobile ? (
    <MailMobileLayout mails={mails} />
  ) : (
    <MailDesktopLayout mails={mails} defaultLayout={defaultLayout} />
  );
}

function MailMobileLayout({ mails }: { mails: Mail[] }) {
  const t = useTranslations("mail");
  const [mail] = useMail();
  const [isMailOpen, setIsMailOpen] = React.useState(false);
  const selectedMail = mails.find((item) => item.id === mail.selected) || null;

  return (
    <>
      <InboxPane mails={mails} onSelectMail={() => setIsMailOpen(true)} />

      <Drawer open={isMailOpen} onOpenChange={setIsMailOpen}>
        <DrawerContent>
          <DrawerTitle className="sr-only">{t("reader.drawerTitle")}</DrawerTitle>
          <DrawerDescription className="sr-only">{t("reader.drawerDescription")}</DrawerDescription>
          <MailView mail={selectedMail} onClose={() => setIsMailOpen(false)} />
        </DrawerContent>
      </Drawer>
    </>
  );
}

function MailDesktopLayout({ mails, defaultLayout }: MailProps & { mails: Mail[] }) {
  const [mail] = useMail();
  const direction = useDirection();
  const layout = defaultLayout ?? DEFAULT_MAIL_LAYOUT;

  const list = (
    <ResizablePanel
      key="list"
      id={MAIL_LIST_PANEL_ID}
      dir={direction}
      defaultSize={`${layout[0]}%`}
      minSize="30%"
      className="min-h-0"
    >
      <InboxPane mails={mails} />
    </ResizablePanel>
  );
  const detail = (
    <ResizablePanel
      key="detail"
      id={MAIL_DETAIL_PANEL_ID}
      dir={direction}
      defaultSize={`${layout[1]}%`}
      minSize="30%"
      className="min-h-0"
    >
      <MailView mail={mails.find((item) => item.id === mail.selected) || null} />
    </ResizablePanel>
  );
  const handle = <ResizableHandle key="handle" withHandle />;

  return (
    // The panels library measures the pointer left to right only. So the group is always laid out left to
    // right, and in a right-to-left language the panels swap places: the list still starts the reading side,
    // and the handle follows the pointer and the arrow keys as the user sees them. A new direction remounts it.
    <ResizablePanelGroup
      key={direction}
      dir="ltr"
      orientation="horizontal"
      onLayoutChanged={(layout) => {
        const sizes = [layout[MAIL_LIST_PANEL_ID], layout[MAIL_DETAIL_PANEL_ID]];
        setClientCookie(MAIL_LAYOUT_COOKIE, JSON.stringify(sizes));
      }}
      className="h-full"
    >
      {direction === "rtl" ? [detail, handle, list] : [list, handle, detail]}
    </ResizablePanelGroup>
  );
}
