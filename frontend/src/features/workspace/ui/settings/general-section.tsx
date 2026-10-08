"use client";

import { useState } from "react";

import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";

import { WORKSPACE_NAME_MAX } from "../../domain/contract";
import { isDomain, suggestedJoinDomain } from "../../domain/people";
import { useWorkspace } from "../../model/use-workspace";
import { updateWorkspace } from "../../model/workspace-actions";
import { SettingRow, SettingsCard } from "./setting-row";

/** The workspace's name, and whether colleagues with a company email can join on their own. */
export function GeneralSection() {
  const t = useTranslations("workspaceSettings");
  const shared = useTranslations("workspace");
  const common = useTranslations("common");
  const { ws, state, can } = useWorkspace();
  const { workspace } = state;
  const [name, setName] = useState(workspace.name);
  const owner = state.members.find((m) => m.role === "owner");
  const [domain, setDomain] = useState(workspace.join_domain ?? suggestedJoinDomain(owner) ?? "");
  const nameChanged = name.trim() !== workspace.name && name.trim().length > 0;
  const domainValid = isDomain(domain.trim().toLowerCase());
  const joining = workspace.join_domain !== null;

  return (
    <SettingsCard id="general" title={t("general.title")}>
      <SettingRow title={t("general.name")} htmlFor="ws-name" description={t("general.nameHint")}>
        <form
          className="flex gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (nameChanged) void updateWorkspace(ws, { name: name.trim() }, t("general.renamed"), shared);
          }}
        >
          <Input
            id="ws-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={WORKSPACE_NAME_MAX}
            disabled={!can.editSettings}
            autoComplete="organization"
            dir="auto"
            className="w-full sm:w-56"
          />
          {can.editSettings ? (
            <Button type="submit" variant="outline" disabled={!nameChanged}>
              {common("actions.save")}
            </Button>
          ) : null}
        </form>
      </SettingRow>
      <SettingRow
        title={t("general.join")}
        htmlFor="ws-join"
        description={joining ? t("general.joinOn", { domain: workspace.join_domain ?? "" }) : t("general.joinHint")}
      >
        <div className="flex items-center gap-2">
          {!joining ? (
            <Input
              aria-label={t("general.domain")}
              value={domain}
              onChange={(event) => setDomain(event.target.value)}
              // i18n-ignore: an example domain, not words
              placeholder="company.com"
              dir="ltr"
              disabled={!can.editSettings}
              className="w-40"
              spellCheck={false}
              autoCapitalize="none"
            />
          ) : null}
          <Switch
            id="ws-join"
            checked={joining}
            disabled={!can.editSettings || (!joining && !domainValid)}
            onCheckedChange={(on) =>
              void updateWorkspace(
                ws,
                { join_domain: on ? domain.trim().toLowerCase() : null },
                on ? t("general.joinEnabled", { domain: domain.trim().toLowerCase() }) : t("general.joinDisabled"),
                shared,
              )
            }
          />
        </div>
      </SettingRow>
    </SettingsCard>
  );
}
