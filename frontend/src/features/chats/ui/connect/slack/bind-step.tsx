"use client";

import { useActionState, useState } from "react";

import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { DialogFooter } from "@/components/ui/dialog";
import { FieldGroup, FieldLegend, FieldSet } from "@/components/ui/field";
import { Spinner } from "@/components/ui/spinner";

import type { ChatMode, ChatSettings } from "../../../domain/contract";
import type { SlackChannel } from "../../../domain/slack-contract";
import { connectChannels } from "../../../model/chat-actions";
import { BindingSelect, DataNotice, ModeField } from "../connect-fields";

/*
 * Привязка каналов и подтверждение: у каждого канала своя привязка, режим и согласие — общие. Shosai хранит
 * сообщения Slack с момента подключения (CF-D3), об этом строка под согласием.
 */

export function BindStep({
  workspaceId,
  settings,
  app,
  installationId,
  picked,
  onBack,
  onDone,
}: {
  workspaceId: string;
  settings: ChatSettings;
  app: string;
  installationId: string;
  picked: SlackChannel[];
  onBack: () => void;
  onDone: () => void;
}) {
  const t = useTranslations("chatsConnect");
  const ta = useTranslations("chatsApi");
  const [bindings, setBindings] = useState<Record<string, string | null>>({});
  const [mode, setMode] = useState<ChatMode>("all");
  const [accepted, setAccepted] = useState(false);
  const [missing, setMissing] = useState(false);
  const [, submit, pending] = useActionState(async () => {
    if (!accepted) {
      setMissing(true);
      document.getElementById("chat-data-notice")?.focus();
      return null;
    }
    const channels = picked.map((c) => ({ channel_id: c.id, project_id: bindings[c.id] ?? null }));
    const body = { installation_id: installationId, channels, mode, data_notice_accepted: true as const };
    if (await connectChannels(workspaceId, body, picked, { t, ta })) onDone();
    return null;
  }, null);

  return (
    <form action={submit} className="flex min-h-0 flex-col gap-4">
      <div className="-mx-1 flex min-h-0 flex-col gap-4 overflow-y-auto px-1">
        <FieldGroup>
          <FieldSet>
            <FieldLegend variant="label">{t("fields.binding")}</FieldLegend>
            <ul className="flex flex-col gap-2">
              {picked.map((channel) => (
                <li key={channel.id} className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)] items-center gap-3">
                  <span dir="auto" className="truncate text-sm">
                    #{channel.name}
                  </span>
                  <BindingSelect
                    id={`slack-binding-${channel.id}`}
                    label={t("slack.bindingFor", { channel: channel.name })}
                    value={bindings[channel.id] ?? null}
                    onChange={(projectId) => setBindings((current) => ({ ...current, [channel.id]: projectId }))}
                  />
                </li>
              ))}
            </ul>
          </FieldSet>
          <ModeField
            value={mode}
            onChange={setMode}
            hints={{ mentions: t("slack.mentionsHint", { app }), all: t("slack.allHint") }}
          />
          <DataNotice
            mode={mode}
            settings={settings}
            checked={accepted}
            invalid={missing && !accepted}
            onChange={(next) => {
              setAccepted(next);
              if (next) setMissing(false);
            }}
          />
        </FieldGroup>
        <p className="text-muted-foreground text-xs">{t("slack.history")}</p>
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onBack}>
          {t("back")}
        </Button>
        <Button type="submit" disabled={pending}>
          {pending ? <Spinner data-icon="inline-start" /> : null}
          {t("slack.connect", { count: picked.length })}
        </Button>
      </DialogFooter>
    </form>
  );
}
