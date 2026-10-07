"use client";

import { useState } from "react";

import { Ban, Download, MoreHorizontal, Rocket, Trash2 } from "lucide-react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Spinner } from "@/components/ui/spinner";

import type { AppRelease } from "../domain/contract";
import { ARCH_LABELS, CHANNEL_LABELS, PLATFORM_LABELS } from "../domain/format";
import { deleteDraft, publishRelease, revokeRelease } from "../model/apps-store";

type Pending = "publish" | "revoke" | "delete";

const CONFIRM: Record<Pending, { title: string; description: string; action: string; destructive: boolean }> = {
  publish: {
    title: "Опубликовать сборку?",
    description: "Сборка станет доступна для скачивания, а приложения получат её как обновление.",
    action: "Опубликовать",
    destructive: false,
  },
  revoke: {
    title: "Отозвать сборку?",
    description:
      "Сборку больше нельзя будет скачать, и обновление перестанет предлагаться. Пользователи, которые уже установили её, останутся на этой версии. Отменить отзыв нельзя.",
    action: "Отозвать",
    destructive: true,
  },
  delete: {
    title: "Удалить черновик?",
    description: "Файл и данные сборки будут удалены без возможности восстановления.",
    action: "Удалить",
    destructive: true,
  },
};

const RUN: Record<Pending, (release: AppRelease) => Promise<unknown>> = {
  publish: publishRelease,
  revoke: revokeRelease,
  delete: deleteDraft,
};

export function ReleaseActions({ release }: { release: AppRelease }) {
  // The action outlives `open` so the dialog keeps its text while it animates closed.
  const [confirm, setConfirm] = useState<{ open: boolean; action: Pending }>({ open: false, action: "publish" });
  const [busy, setBusy] = useState(false);
  const name = `${PLATFORM_LABELS[release.platform]} ${release.version} (${ARCH_LABELS[release.arch]}, ${CHANNEL_LABELS[release.channel]})`;
  const dialog = CONFIRM[confirm.action];
  const ask = (action: Pending) => setConfirm({ open: true, action });

  const run = (action: Pending) => {
    setConfirm((c) => ({ ...c, open: false }));
    setBusy(true);
    void RUN[action](release).finally(() => setBusy(false));
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon-sm" disabled={busy} aria-label={`Действия: ${name}`}>
            {busy ? <Spinner /> : <MoreHorizontal />}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          {release.status === "draft" ? (
            <DropdownMenuItem onSelect={() => ask("publish")}>
              <Rocket />
              Опубликовать
            </DropdownMenuItem>
          ) : null}
          <DropdownMenuItem asChild>
            <a href={release.download_url} download={release.file_name}>
              <Download />
              Скачать
            </a>
          </DropdownMenuItem>
          {release.status === "published" ? (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem variant="destructive" onSelect={() => ask("revoke")}>
                <Ban />
                Отозвать
              </DropdownMenuItem>
            </>
          ) : null}
          {release.status === "draft" ? (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem variant="destructive" onSelect={() => ask("delete")}>
                <Trash2 />
                Удалить черновик
              </DropdownMenuItem>
            </>
          ) : null}
        </DropdownMenuContent>
      </DropdownMenu>

      <AlertDialog open={confirm.open} onOpenChange={(open) => setConfirm((c) => ({ ...c, open }))}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{dialog.title}</AlertDialogTitle>
            <AlertDialogDescription>
              <span className="font-medium text-foreground">{name}</span>. {dialog.description}
              {confirm.action === "publish" && release.mandatory
                ? " Обновление обязательное и установится без вопросов."
                : null}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Отмена</AlertDialogCancel>
            <AlertDialogAction
              variant={dialog.destructive ? "destructive" : "default"}
              onClick={() => void run(confirm.action)}
            >
              {dialog.action}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
