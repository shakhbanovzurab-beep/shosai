"use client";

import { UserPlus, Users, UsersRound } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

import { adminContactName } from "../../domain/roles";
import { openInviteDialog } from "../../model/invite-dialog-store";
import { useWorkspace } from "../../model/use-workspace";
import { TeamPage, TeamPageHeader } from "../shared/layout";
import { replaceUrl } from "../shared/replace-url";
import { MembersTab } from "./members-tab";
import { SeatMeter } from "./seat-meter";
import { TeamsTab } from "./teams-tab";

export type MembersTabId = "members" | "teams";

/** People and teams of the workspace, with the seat meter and the one way in: Invite people. */
export function MembersScreen({ initialTab }: { initialTab: MembersTabId }) {
  const t = useTranslations("workspaceMembers");
  const { state, can, path } = useWorkspace();
  const contact = adminContactName(state);

  const invite = can.invite ? (
    <Button onClick={openInviteDialog}>
      <UserPlus data-icon="inline-start" />
      {t("invitePeople")}
    </Button>
  ) : (
    <Tooltip>
      <TooltipTrigger asChild>
        {/* aria-disabled rather than disabled: the button stays focusable, so the reason can be read. */}
        <Button aria-disabled="true" className="opacity-50" onClick={(event) => event.preventDefault()}>
          <UserPlus data-icon="inline-start" />
          {t("invitePeople")}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{contact ? t("adminsInviteAsk", { name: contact }) : t("adminsInvite")}</TooltipContent>
    </Tooltip>
  );

  return (
    <TeamPage>
      <TeamPageHeader
        title={t("title")}
        description={t("description", { workspace: state.workspace.name })}
        actions={invite}
      />
      <SeatMeter state={state} canBuy={can.manageBilling} />
      <Tabs
        defaultValue={initialTab}
        onValueChange={(value) => replaceUrl(path(value === "teams" ? "/members?tab=teams" : "/members"))}
        className="gap-6"
      >
        <TabsList variant="line" className="w-full justify-start border-b">
          <TabsTrigger value="members" className="flex-none">
            <Users />
            {t("tabs.members")}
          </TabsTrigger>
          <TabsTrigger value="teams" className="flex-none">
            <UsersRound />
            {t("tabs.teams")}
          </TabsTrigger>
        </TabsList>
        <TabsContent value="members">
          <MembersTab />
        </TabsContent>
        <TabsContent value="teams">
          <TeamsTab />
        </TabsContent>
      </Tabs>
    </TeamPage>
  );
}
