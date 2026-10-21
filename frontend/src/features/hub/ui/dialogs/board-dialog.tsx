"use client";

import { useState } from "react";

import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Skeleton } from "@/components/ui/skeleton";
import { useBoards } from "@/features/kanban/model/boards-resource";
import { Link } from "@/lib/navigation";

import type { Hub } from "../../domain/contract";
import { boardPath } from "../../domain/paths";
import { chooseBoard } from "../../model/hub-actions";
import { useHubWords } from "../../model/words";
import { SubmitButton } from "../shared/submit-button";

const NONE = "none";

/** The boards to choose from, with "No board" first: a hub may have nowhere to send work, and says so. */
function BoardChoices({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const t = useTranslations("hub");
  const boards = useBoards();
  if (boards.status === "loading")
    return (
      <div className="flex flex-col gap-3" aria-busy="true">
        <Skeleton className="h-5 w-1/3" />
        <Skeleton className="h-5 w-1/2" />
        <Skeleton className="h-5 w-2/5" />
      </div>
    );
  if (boards.status === "error") return <p className="text-muted-foreground text-sm">{t("dialogs.boardsError")}</p>;
  const options = [{ id: NONE, name: t("dialogs.boardNone") }, ...boards.data.items];
  return (
    <RadioGroup value={value} onValueChange={onChange} aria-label={t("dialogs.boardTitle")} className="gap-3">
      {options.map((board) => (
        <div key={board.id} className="flex items-center gap-2.5">
          <RadioGroupItem value={board.id} id={`board-${board.id}`} />
          <Label htmlFor={`board-${board.id}`} className="font-normal">
            {board.name}
          </Label>
        </div>
      ))}
    </RadioGroup>
  );
}

function BoardForm({ hub, onDone }: { hub: Hub; onDone: () => void }) {
  const t = useTranslations("hub");
  const common = useTranslations("common");
  const words = useHubWords();
  const [value, setValue] = useState(hub.boardId ?? NONE);
  return (
    <form
      className="flex flex-col gap-5"
      action={async () => {
        if (await chooseBoard(words, hub, value === NONE ? null : value)) onDone();
      }}
    >
      <DialogHeader>
        <DialogTitle>{t("dialogs.boardTitle")}</DialogTitle>
        <DialogDescription>{t("dialogs.boardText")}</DialogDescription>
      </DialogHeader>
      <BoardChoices value={value} onChange={setValue} />
      <DialogFooter className="sm:justify-between">
        {hub.boardId && hub.boardName ? (
          <Button asChild variant="link" className="justify-start px-0">
            <Link href={boardPath(hub.boardId)}>{t("dialogs.openBoard")}</Link>
          </Button>
        ) : (
          <span />
        )}
        <div className="flex flex-col-reverse gap-2 sm:flex-row">
          <DialogClose asChild>
            <Button type="button" variant="outline">
              {common("actions.cancel")}
            </Button>
          </DialogClose>
          <SubmitButton>{common("actions.save")}</SubmitButton>
        </div>
      </DialogFooter>
    </form>
  );
}

/** Where the hub's work goes: a board, or explicitly none. */
export function BoardDialog({ hub, onOpenChange }: { hub: Hub | null; onOpenChange: (open: boolean) => void }) {
  return (
    <Dialog open={hub !== null} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        {hub ? <BoardForm key={hub.id} hub={hub} onDone={() => onOpenChange(false)} /> : null}
      </DialogContent>
    </Dialog>
  );
}
