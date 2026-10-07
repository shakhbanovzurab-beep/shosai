"use client";

import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";

import { formatBytes } from "../domain/format";
import type { UploadPhase } from "../model/use-upload";

type UploadFooterProps = { phase: UploadPhase; error: string | null; onCancel: () => void; onClose: () => void };

/** Progress, the server's error, and the form's buttons. */
export function UploadFooter({ phase, error, onCancel, onClose }: UploadFooterProps) {
  const busy = phase.status !== "editing";
  const percent = phase.status === "uploading" && phase.total > 0 ? Math.round((phase.loaded / phase.total) * 100) : 0;

  return (
    <div className="flex flex-col gap-3 border-t p-4">
      {phase.status === "uploading" || phase.status === "processing" ? (
        <div className="flex flex-col gap-1.5" aria-live="polite">
          <Progress
            value={phase.status === "processing" ? 100 : percent}
            aria-label="Прогресс загрузки"
            aria-valuetext={phase.status === "processing" ? "Проверка файла" : `${percent}%`}
          />
          <p className="text-muted-foreground text-xs tabular-nums">
            {phase.status === "processing"
              ? "Файл передан, сервер проверяет контрольную сумму…"
              : `${formatBytes(phase.loaded)} из ${formatBytes(phase.total)} · ${percent}%`}
          </p>
        </div>
      ) : null}
      {phase.status === "hashing" ? (
        <p className="text-muted-foreground text-xs" aria-live="polite">
          Вычисляем SHA-256…
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="text-destructive text-sm">
          {error}
        </p>
      ) : null}
      <div className="flex justify-end gap-2">
        {busy ? (
          <Button type="button" variant="outline" onClick={onCancel}>
            Отменить загрузку
          </Button>
        ) : (
          <Button type="button" variant="ghost" onClick={onClose}>
            Закрыть
          </Button>
        )}
        <Button type="submit" disabled={busy}>
          {busy ? <Spinner data-icon="inline-start" /> : null}
          {busy ? "Загрузка…" : "Загрузить черновик"}
        </Button>
      </div>
    </div>
  );
}
