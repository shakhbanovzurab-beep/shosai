"use client";

import { Badge } from "@/components/ui/badge";
import { TableCell, TableRow } from "@/components/ui/table";

import type { AppRelease, ReleaseStatus } from "../domain/contract";
import { ARCH_LABELS, CHANNEL_LABELS, formatBytes, formatCount, formatDateTime, STATUS_LABELS } from "../domain/format";
import { ReleaseActions } from "./release-actions";
import { RolloutControl } from "./rollout-control";

const STATUS_VARIANTS: Record<ReleaseStatus, "outline" | "secondary" | "destructive"> = {
  draft: "outline",
  published: "secondary",
  revoked: "destructive",
};

export function ReleaseRow({ release }: { release: AppRelease }) {
  return (
    <TableRow>
      <TableCell>
        <div className="flex flex-col gap-0.5">
          <span className="flex items-center gap-2 font-medium tabular-nums">
            {release.version}
            {release.mandatory ? <Badge variant="outline">Обязательное</Badge> : null}
          </span>
          <span className="max-w-56 truncate text-muted-foreground text-xs" title={release.file_name}>
            {release.file_name}
          </span>
        </div>
      </TableCell>
      <TableCell>{CHANNEL_LABELS[release.channel]}</TableCell>
      <TableCell>{ARCH_LABELS[release.arch]}</TableCell>
      <TableCell className="text-right tabular-nums">{formatBytes(release.size_bytes)}</TableCell>
      <TableCell>
        <div className="flex flex-col gap-0.5">
          <span>{release.uploaded_by}</span>
          <time className="text-muted-foreground text-xs" dateTime={release.uploaded_at}>
            {formatDateTime(release.uploaded_at)}
          </time>
        </div>
      </TableCell>
      <TableCell>
        <Badge variant={STATUS_VARIANTS[release.status]}>{STATUS_LABELS[release.status]}</Badge>
      </TableCell>
      <TableCell>
        {release.status === "published" && release.channel === "stable" ? (
          <RolloutControl key={release.rollout_percent} release={release} />
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </TableCell>
      <TableCell className="text-right tabular-nums">{formatCount(release.downloads)}</TableCell>
      <TableCell className="text-right">
        <ReleaseActions release={release} />
      </TableCell>
    </TableRow>
  );
}
