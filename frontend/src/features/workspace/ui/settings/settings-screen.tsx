"use client";

import { Info } from "lucide-react";
import { useTranslations } from "use-intl";

import { Alert, AlertDescription } from "@/components/ui/alert";

import { adminContactName } from "../../domain/roles";
import { useWorkspace } from "../../model/use-workspace";
import { TeamPage, TeamPageHeader } from "../shared/layout";
import { DangerZone } from "./danger-zone";
import { GeneralSection } from "./general-section";
import { PlanSection } from "./plan-section";
import { SharingSection } from "./sharing-section";

/** Workspace settings on one page: general, sharing rules, plan and usage, and leaving or deleting it. */
export function TeamSettingsScreen() {
  const t = useTranslations("workspaceSettings");
  const { state, can } = useWorkspace();
  const contact = adminContactName(state);
  return (
    <TeamPage className="max-w-3xl">
      <TeamPageHeader title={t("title")} description={t("description", { workspace: state.workspace.name })} />
      {!can.editSettings ? (
        <Alert>
          <Info />
          <AlertDescription>{contact ? t("adminsOnlyAsk", { name: contact }) : t("adminsOnly")}</AlertDescription>
        </Alert>
      ) : null}
      <GeneralSection />
      <SharingSection />
      {can.admin ? <PlanSection /> : null}
      <DangerZone />
    </TeamPage>
  );
}
