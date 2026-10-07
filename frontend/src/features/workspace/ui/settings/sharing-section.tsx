"use client";

import { ShieldCheck } from "lucide-react";
import { useTranslations } from "next-intl";

import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";

import { DEFAULT_SHARE_LEVELS, type DefaultShareLevel, type SharingPolicy } from "../../domain/contract";
import { useWorkspace } from "../../model/use-workspace";
import { updateWorkspace } from "../../model/workspace-actions";
import { SettingRow, SettingsCard } from "./setting-row";

const isLevel = (value: string): value is DefaultShareLevel => DEFAULT_SHARE_LEVELS.some((l) => l === value);

/**
 * Where meeting notes go by default. Meetings with guests are always held back, so a wrong default can
 * never send a transcript outside the company.
 */
export function SharingSection() {
  const t = useTranslations("workspaceSettings");
  const shared = useTranslations("workspace");
  const { ws, state, can } = useWorkspace();
  const { sharing, name } = state.workspace;
  const save = (change: Partial<SharingPolicy>, message: string) =>
    void updateWorkspace(ws, { sharing: change }, message, shared);
  const levelLabel = (level: DefaultShareLevel) => t(`sharing.levels.${level}`, { workspace: name });

  return (
    <SettingsCard id="sharing" title={t("sharing.title")} description={t("sharing.description", { workspace: name })}>
      {!state.workspace.sharing_reviewed && can.editSettings ? (
        <Alert className="mb-4">
          <ShieldCheck />
          <AlertTitle>{t("sharing.reviewTitle")}</AlertTitle>
          <AlertDescription>{t("sharing.reviewHint")}</AlertDescription>
          <AlertAction>
            <Button size="sm" variant="outline" onClick={() => save({}, t("sharing.confirmed"))}>
              {t("sharing.keep")}
            </Button>
          </AlertAction>
        </Alert>
      ) : null}
      <SettingRow
        title={t("sharing.defaultLevel")}
        htmlFor="ws-default-level"
        description={t("sharing.defaultLevelHint", { workspace: name })}
      >
        <Select
          value={sharing.default_level}
          disabled={!can.editSettings}
          onValueChange={(value) => {
            if (isLevel(value)) save({ default_level: value }, t("sharing.levelChanged", { level: levelLabel(value) }));
          }}
        >
          <SelectTrigger id="ws-default-level" className="w-full sm:w-60">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {DEFAULT_SHARE_LEVELS.map((level) => (
                <SelectItem key={level} value={level}>
                  {levelLabel(level)}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      </SettingRow>
      <SettingRow title={t("sharing.transcripts")} htmlFor="ws-transcripts" description={t("sharing.transcriptsHint")}>
        <Switch
          id="ws-transcripts"
          checked={sharing.share_transcripts}
          disabled={!can.editSettings}
          onCheckedChange={(on) =>
            save({ share_transcripts: on }, t(on ? "sharing.transcriptsOn" : "sharing.transcriptsOff"))
          }
        />
      </SettingRow>
      <SettingRow title={t("sharing.membersInvite")} htmlFor="ws-invite" description={t("sharing.membersInviteHint")}>
        <Switch
          id="ws-invite"
          checked={sharing.members_can_invite}
          disabled={!can.editSettings}
          onCheckedChange={(on) =>
            save({ members_can_invite: on }, t(on ? "sharing.membersInviteOn" : "sharing.membersInviteOff"))
          }
        />
      </SettingRow>
    </SettingsCard>
  );
}
