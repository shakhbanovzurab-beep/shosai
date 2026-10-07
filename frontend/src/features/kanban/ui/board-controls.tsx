"use client";

import { useState } from "react";

import { useRouter } from "next/navigation";

import { useTranslations } from "next-intl";

import { ConfirmDestructive } from "@/components/feedback";
import { NameDialog } from "@/components/name-dialog";

import type { BoardSummary } from "../domain/board";
import { deleteBoard, updateBoard } from "../model/board-actions";
import { type BoardMenuIntent, BoardSwitcher } from "./board-switcher";
import { JiraBoardDialog } from "./jira-board-dialog";
import { NewBoardDialog } from "./new-board-dialog";

/** The board switcher and the dialogs it opens: new board, Jira board, rename and delete. */
export function BoardControls({ boards, current }: { boards: BoardSummary[]; current: BoardSummary }) {
  const router = useRouter();
  const t = useTranslations("kanbanBoards");
  const tc = useTranslations("common");
  const [intent, setIntent] = useState<BoardMenuIntent | null>(null);
  const close = () => setIntent(null);
  const openChange = (which: BoardMenuIntent) => (open: boolean) => setIntent(open ? which : null);

  return (
    <>
      <BoardSwitcher boards={boards} current={current} onIntent={setIntent} />
      <NewBoardDialog open={intent === "new"} onOpenChange={openChange("new")} />
      <JiraBoardDialog open={intent === "jira"} onOpenChange={openChange("jira")} />
      <NameDialog
        request={
          intent === "rename"
            ? {
                title: t("renameTitle"),
                initial: current.name,
                submitLabel: tc("actions.rename"),
                onSubmit: (name) => void updateBoard(current.id, { name }, t),
              }
            : null
        }
        onClose={close}
      />
      <ConfirmDestructive
        open={intent === "delete"}
        title={t(current.jira ? "delete.stopTitle" : "delete.title", { board: current.name })}
        description={
          current.jira ? t("delete.stopDescription") : t("delete.description", { count: current.task_count })
        }
        confirmLabel={current.jira ? t("delete.stopConfirm") : t("delete.confirm")}
        cancelLabel={tc("actions.cancel")}
        onCancel={close}
        onConfirm={() => {
          close();
          void deleteBoard(current, t).then((deleted) => (deleted ? router.push("/app/kanban") : undefined));
        }}
      />
    </>
  );
}
