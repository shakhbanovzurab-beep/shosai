"use client";

import { type ReactNode, useState } from "react";

import { useTranslations } from "use-intl";

import { ConfirmDestructive } from "@/components/feedback";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SettingRow } from "@/features/workspace/ui/settings/setting-row";

import { shortensRetention } from "../../domain/chat-rules";
import { type ChatSettings, RETENTION_DAYS, type RetentionDays } from "../../domain/contract";
import { setRetention } from "../../model/chat-actions";

/*
 * Где и сколько хранятся сообщения подключённых чатов (CF-D8): срок меняет админ, укороченный срок стирает
 * старые сообщения — поэтому сначала подтверждение; регион — дом данных пространства.
 */

const isRetention = (value: number): value is RetentionDays => RETENTION_DAYS.some((days) => days === value);

/** Выбор срока для админа: короче нынешнего — только после подтверждения. */
export function RetentionControl({ workspaceId, current }: { workspaceId: string; current: RetentionDays }) {
  const t = useTranslations("chats");
  const ta = useTranslations("chatsApi");
  const [shorter, setShorter] = useState<RetentionDays | null>(null);
  const daysText = (days: RetentionDays) => t("retention.days", { count: days });
  const save = (days: RetentionDays) =>
    void setRetention(workspaceId, days, t("retention.saved", { days: daysText(days) }), ta);

  return (
    <>
      <Select
        value={String(current)}
        onValueChange={(value) => {
          const days = Number(value);
          if (!isRetention(days) || days === current) return;
          if (shortensRetention(current, days)) setShorter(days);
          else save(days);
        }}
      >
        <SelectTrigger id="chats-retention" className="w-full sm:w-40">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            {RETENTION_DAYS.map((days) => (
              <SelectItem key={days} value={String(days)}>
                {daysText(days)}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
      <ConfirmDestructive
        open={shorter !== null}
        title={t("retention.shorterTitle", { days: daysText(shorter ?? current) })}
        description={t("retention.shorterBody", { days: daysText(shorter ?? current) })}
        confirmLabel={t("retention.shorterConfirm")}
        onConfirm={() => {
          if (shorter !== null) save(shorter);
          setShorter(null);
        }}
        onCancel={() => setShorter(null)}
      />
    </>
  );
}

/** Срок текстом — для участника, который его не меняет. */
export function RetentionText({ current }: { current: RetentionDays }) {
  const t = useTranslations("chats");
  return <span className="text-sm tabular-nums">{t("retention.days", { count: current })}</span>;
}

/** Строка хранения под списком: срок и где лежат сообщения; `control` — выбор срока или его текст. */
export function StorageRow({ settings, control }: { settings: ChatSettings; control: ReactNode }) {
  const t = useTranslations("chats");
  return (
    <SettingRow
      title={t("retention.title")}
      htmlFor="chats-retention"
      description={t("retention.hint", { home: settings.home })}
    >
      {control}
    </SettingRow>
  );
}
