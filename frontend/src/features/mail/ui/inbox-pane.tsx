"use client";

import * as React from "react";

import { cn } from "cn";
import { Ellipsis, RotateCcw, SlidersHorizontal } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";

import { dropdownKit } from "@/components/menu-kit";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar-panel";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { briefInbox, type InboxView } from "../domain/leo-triage";
import type { Mail } from "../domain/mail";
import { insightsResource, useLeoInbox } from "../model/leo-insights";
import { useMail } from "../model/use-mail";
import { LeoFocusList } from "./leo-focus-list";
import { LeoInboxStatus } from "./leo-inbox-status";
import { MailList } from "./mail-list";
import { MailMenuItems } from "./mail-menu";

interface InboxPaneProps {
  mails: Mail[];
  onSelectMail?: (mail: Mail) => void;
}

/** The inbox column: header actions, then Leo's "Needs you" queue or all mail, pinned first. */
export function InboxPane({ mails, onSelectMail }: InboxPaneProps) {
  const t = useTranslations("mail");
  const common = useTranslations("common");
  const format = useFormatter();
  const [{ selected }] = useMail();
  const [inboxView, setInboxView] = React.useState<InboxView>("focus");
  const { state, views } = useLeoInbox();
  const inbox = mails.filter((mail) => mail.folder === "inbox");
  const pinnedMails = inbox.filter((mail) => mail.isPinned);
  const unpinnedMails = inbox.filter((mail) => !mail.isPinned);
  const selectedMail = inbox.find((mail) => mail.id === selected);
  const brief = briefInbox(mails, views);
  const isRefreshing = state.status === "ready" && state.refreshing;
  const showAll = () => setInboxView("all");

  return (
    <Tabs
      value={inboxView}
      onValueChange={(value) => setInboxView(value === "all" ? "all" : "focus")}
      className="flex h-full min-h-0 flex-col gap-3 pt-3"
    >
      <div className="flex items-center justify-between gap-4 px-2">
        <div className="flex items-center">
          <SidebarTrigger />
          <Separator orientation="vertical" className="ms-1 me-2 h-4 data-vertical:self-center" />
          <h1 className="font-medium text-xl leading-none">{t("nav.inbox")}</h1>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon-sm" aria-label={t("inbox.filter")}>
            <SlidersHorizontal />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={t("inbox.refresh")}
            disabled={isRefreshing}
            onClick={() => void insightsResource.refresh()}
          >
            <RotateCcw className={cn(isRefreshing && "motion-safe:animate-spin")} />
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={
                  selectedMail ? common("actionsFor", { name: selectedMail.subject }) : t("inbox.noSelection")
                }
                disabled={!selectedMail}
              >
                <Ellipsis />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              {selectedMail ? <MailMenuItems kit={dropdownKit} mail={selectedMail} /> : null}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <div className="flex flex-col gap-3 px-2">
        <Separator />
        <TabsList className="w-full">
          <TabsTrigger value="focus">
            {t("inbox.needsYou")}
            {state.status === "ready" ? (
              <Badge variant="secondary" className="tabular-nums">
                {format.number(brief.waiting.length)}
              </Badge>
            ) : null}
          </TabsTrigger>
          <TabsTrigger value="all">
            {t("inbox.allMail")}
            <Badge variant="secondary" className="tabular-nums">
              {format.number(inbox.length)}
            </Badge>
          </TabsTrigger>
        </TabsList>
      </div>

      <TabsContent value="focus" className="flex min-h-0 flex-col gap-1.5">
        <LeoFocusList state={state} views={views} brief={brief} onSelectMail={onSelectMail} onShowAll={showAll} />
      </TabsContent>
      <TabsContent value="all" className="flex min-h-0 flex-col gap-1.5">
        <div className="px-3">
          <LeoInboxStatus state={state} brief={brief} />
        </div>
        <MailList
          groups={[
            { id: "pinned", title: t("inbox.pinnedGroup", { count: pinnedMails.length }), items: pinnedMails },
            { id: "inbox", title: t("inbox.inboxGroup", { count: unpinnedMails.length }), items: unpinnedMails },
          ]}
          views={views}
          inboxView="all"
          onSelectMail={onSelectMail}
        />
      </TabsContent>
    </Tabs>
  );
}
