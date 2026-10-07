"use client";

import { Download, Laptop, Monitor } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

import {
  type AppPlatform,
  type AppRelease,
  EXTENSIONS_BY_PLATFORM,
  RELEASE_CHANNELS,
  type ReleaseChannel,
} from "../domain/contract";
import { ARCH_LABELS, CHANNEL_LABELS, formatBytes, formatCount, formatDate, PLATFORM_LABELS } from "../domain/format";
import { currentVersion } from "../domain/release-rules";
import { Sha256Text } from "./sha256-text";

const PLATFORM_ICONS = { macos: Laptop, windows: Monitor } as const;

export function PlatformCard({ platform, releases }: { platform: AppPlatform; releases: readonly AppRelease[] }) {
  const Icon = PLATFORM_ICONS[platform];
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <span className="flex size-9 items-center justify-center rounded-lg bg-muted">
            <Icon className="size-4" aria-hidden="true" />
          </span>
          <div className="flex min-w-0 flex-col gap-0.5">
            <CardTitle>{PLATFORM_LABELS[platform]}</CardTitle>
            <CardDescription>Форматы: {EXTENSIONS_BY_PLATFORM[platform].join(", ")}</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {RELEASE_CHANNELS.map((channel, index) => (
          <section key={channel} aria-label={`${PLATFORM_LABELS[platform]}, канал «${CHANNEL_LABELS[channel]}»`}>
            {index > 0 ? <Separator className="mb-4" /> : null}
            <ChannelSummary channel={channel} files={currentVersion(releases, platform, channel)} />
          </section>
        ))}
      </CardContent>
    </Card>
  );
}

function ChannelSummary({ channel, files }: { channel: ReleaseChannel; files: AppRelease[] }) {
  const head = files.at(0);
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-medium text-sm">{CHANNEL_LABELS[channel]}</h3>
        {head ? (
          <>
            <Badge variant="secondary" className="tabular-nums">
              {head.version}
            </Badge>
            {files.some((f) => f.mandatory) ? <Badge variant="outline">Обязательное</Badge> : null}
            {head.rollout_percent < 100 ? (
              <Badge variant="outline" className="tabular-nums">
                Раскатка {head.rollout_percent}%
              </Badge>
            ) : null}
            {head.published_at ? (
              <span className="text-muted-foreground text-xs">опубликовано {formatDate(head.published_at)}</span>
            ) : null}
          </>
        ) : null}
      </div>
      {head ? (
        <ul className="flex flex-col gap-2">
          {files.map((file) => (
            <li key={file.id} className="flex flex-col gap-2 rounded-lg border p-3 sm:flex-row sm:items-center">
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <div className="flex min-w-0 items-center gap-2">
                  <span className="truncate font-medium text-sm" title={file.file_name}>
                    {file.file_name}
                  </span>
                  <Badge variant="outline" className="shrink-0">
                    {ARCH_LABELS[file.arch]}
                  </Badge>
                </div>
                <p className="text-muted-foreground text-xs tabular-nums">
                  {formatBytes(file.size_bytes)} · {formatCount(file.downloads)} загрузок
                </p>
                <Sha256Text value={file.sha256} />
              </div>
              <Button asChild variant="outline" size="sm" className="self-start sm:self-center">
                <a href={file.download_url} download={file.file_name}>
                  <Download data-icon="inline-start" />
                  Скачать
                </a>
              </Button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="rounded-lg border border-dashed p-3 text-muted-foreground text-sm">
          Нет опубликованных сборок в этом канале.
        </p>
      )}
    </div>
  );
}
