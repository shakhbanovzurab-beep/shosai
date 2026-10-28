import { lazy, Suspense } from "react";

import { AlertTriangle, Check, Eye, RefreshCw, X } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

import type { BoardSession } from "../../domain/board";
import { withBoardAssets } from "../../model/board-editor";
import { useBoardState } from "../../model/board-state";

// Excalidraw — отдельным чанком: страница комнаты без доски его не грузит.
const BoardCanvas = lazy(() => withBoardAssets(() => import("./board-canvas")));

/** Доска на месте сцены: состояние сохранения, только чтение после звонка, закрыть. */
export function BoardPanel({ board, onClose }: { board: BoardSession; onClose: () => void }) {
  const t = useTranslations("meetingRoom");
  const { save, readOnly } = useBoardState(board);
  return (
    <section
      aria-label={t("board.label")}
      className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border bg-card"
    >
      <div className="flex items-center gap-2 border-b px-3 py-2 text-sm">
        <span role="status" className="flex items-center gap-1.5 text-muted-foreground">
          {readOnly ? <Eye aria-hidden="true" className="size-4" /> : null}
          {!readOnly && save === "saved" ? <Check aria-hidden="true" className="size-4" /> : null}
          {!readOnly && (save === "saving" || save === "loading") ? <Spinner /> : null}
          {save === "conflict" || save === "too_large" || save === "failed" ? (
            <AlertTriangle aria-hidden="true" className="size-4 text-destructive" />
          ) : null}
          {t(readOnly ? "board.readOnly" : `board.save.${save}`)}
        </span>
        {save === "conflict" ? (
          <Button variant="outline" size="sm" onClick={() => void board.reload()}>
            <RefreshCw data-icon="inline-start" />
            {t("board.reload")}
          </Button>
        ) : null}
        <Button variant="ghost" size="icon-sm" className="ms-auto" aria-label={t("board.close")} onClick={onClose}>
          <X aria-hidden="true" />
        </Button>
      </div>
      <div className="min-h-0 flex-1">
        <Suspense
          fallback={
            <div className="flex size-full items-center justify-center gap-2 text-muted-foreground text-sm">
              <Spinner />
              {t("board.loading")}
            </div>
          }
        >
          <BoardCanvas board={board} />
        </Suspense>
      </div>
    </section>
  );
}
