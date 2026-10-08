"use client";

import { useState } from "react";

import { Download } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";

import { DATA_KINDS, type DataKind } from "../../domain/data-contract";
import { SettingsGroup, SettingsRow } from "../settings-row";
import { DataListDialog } from "./data-list-dialog";

/** Privacy › Your data: download everything, and manage what's shared, uploaded or rated. */
export function YourData() {
  const t = useTranslations("settingsPrivacy");
  const words = useTranslations("settings");
  const [managing, setManaging] = useState<DataKind | null>(null);

  return (
    <SettingsGroup title={t("yourData")}>
      <SettingsRow title={t("export")} description={t("exportHint")}>
        <Button variant="outline" asChild>
          <a href="/api/settings/data/export" download>
            <Download data-icon="inline-start" />
            {t("export")}
          </a>
        </Button>
      </SettingsRow>
      {DATA_KINDS.map((kind) => (
        <SettingsRow key={kind} title={t(`kinds.${kind}.title`)}>
          <Button variant="outline" onClick={() => setManaging(kind)}>
            {words("manage")}
          </Button>
        </SettingsRow>
      ))}
      {managing ? <DataListDialog key={managing} kind={managing} onClose={() => setManaging(null)} /> : null}
    </SettingsGroup>
  );
}
