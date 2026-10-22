"use client";

import { useDeferredValue, useState } from "react";

import { Lock, Search } from "lucide-react";
import { useTranslations } from "use-intl";

import { LoadError } from "@/components/feedback";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { DialogFooter } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { FieldLabel } from "@/components/ui/field-text";
import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group";
import { Skeleton } from "@/components/ui/skeleton";

import { SLACK_CHANNELS_PER_CONNECT, type SlackChannel } from "../../../domain/slack-contract";
import { chatResources, useChannels } from "../../../model/resources";
import { CopyValue } from "../copy-value";

/*
 * Каналы установки: поиск по названию, отметки (до 20 за раз), подключённые — неактивны. Закрытый канал
 * виден, только когда Leo уже в нём, поэтому здесь же команда приглашения.
 */

function ChannelOption({
  channel,
  checked,
  onToggle,
}: {
  channel: SlackChannel;
  checked: boolean;
  onToggle: () => void;
}) {
  const t = useTranslations("chatsConnect");
  const id = `slack-channel-${channel.id}`;
  const connected = channel.connection_id !== null;
  return (
    <Field orientation="horizontal" data-disabled={connected || undefined} className="py-2">
      <Checkbox id={id} checked={checked || connected} disabled={connected} onCheckedChange={onToggle} />
      <FieldLabel htmlFor={id} className="flex min-w-0 flex-1 items-center gap-2 font-normal">
        <span dir="auto" className="min-w-0 truncate">
          #{channel.name}
        </span>
        {channel.private ? <Lock aria-label={t("slack.private")} className="size-3.5 text-muted-foreground" /> : null}
        <span className="ms-auto shrink-0 text-muted-foreground text-xs tabular-nums">
          {connected ? (
            <Badge variant="secondary">{t("slack.alreadyIn")}</Badge>
          ) : (
            t("slack.members", { count: channel.member_count ?? 0 })
          )}
        </span>
      </FieldLabel>
    </Field>
  );
}

export function ChannelsStep({
  workspaceId,
  installationId,
  app,
  initial,
  onBack,
  onNext,
}: {
  workspaceId: string;
  installationId: string;
  app: string;
  initial: SlackChannel[];
  onBack: () => void;
  onNext: (picked: SlackChannel[]) => void;
}) {
  const t = useTranslations("chatsConnect");
  const tc = useTranslations("common");
  const [query, setQuery] = useState("");
  const [picked, setPicked] = useState<SlackChannel[]>(initial);
  const q = useDeferredValue(query.trim());
  const state = useChannels(workspaceId, installationId, q);
  const toggle = (channel: SlackChannel) =>
    setPicked((current) => {
      if (current.some((c) => c.id === channel.id)) return current.filter((c) => c.id !== channel.id);
      return current.length < SLACK_CHANNELS_PER_CONNECT ? [...current, channel] : current;
    });

  return (
    <div className="flex min-h-0 flex-col gap-4">
      <InputGroup>
        <InputGroupAddon>
          <Search />
        </InputGroupAddon>
        <InputGroupInput
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("slack.search")}
          aria-label={t("slack.searchLabel")}
          spellCheck={false}
          autoComplete="off"
        />
      </InputGroup>
      <div className="-mx-1 flex min-h-32 flex-col overflow-y-auto px-1">
        {state.status === "loading" ? <Skeleton className="h-24 w-full" /> : null}
        {state.status === "error" ? (
          <LoadError
            title={t("slack.channelsError")}
            message={t("slack.loadErrorHint")}
            retryLabel={tc("actions.retry")}
            onRetry={() => void chatResources(workspaceId).channels(installationId, q).refresh()}
          />
        ) : null}
        {state.status === "ready" && state.data.items.length === 0 ? (
          <p className="py-6 text-center text-muted-foreground text-sm">{t("slack.noChannels")}</p>
        ) : null}
        {state.status === "ready"
          ? state.data.items.map((channel) => (
              <ChannelOption
                key={channel.id}
                channel={channel}
                checked={picked.some((c) => c.id === channel.id)}
                onToggle={() => toggle(channel)}
              />
            ))
          : null}
      </div>
      <div className="flex flex-col gap-1.5">
        <p className="text-muted-foreground text-xs">{t("slack.privateHint")}</p>
        <CopyValue
          value={`/invite @${app}`}
          shown={`/invite @${app}`}
          copyLabel={t("add.copyCommand")}
          copied={t("add.commandCopied")}
          size="command"
        />
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onBack}>
          {t("back")}
        </Button>
        <Button type="button" disabled={picked.length === 0} onClick={() => onNext(picked)}>
          {t("slack.continue", { count: picked.length })}
        </Button>
      </DialogFooter>
    </div>
  );
}
