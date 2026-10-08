"use client";

import { useState } from "react";

import { CirclePause, CirclePlay, Crown, EllipsisVertical, Trash2, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu-items";

import type { AdminWorkspaceDetail } from "../domain/contract";
import { formatNumber } from "../domain/format";
import { resume } from "../model/actions";
import { DeleteDialog, SuspendDialog } from "./access-dialogs";
import { OwnerDialog, SeatsDialog } from "./plan-dialogs";

type Opening = "seats" | "owner" | "suspend" | "delete" | null;

/** Seats, ownership, access and deletion: each opens a dialog that says what will happen first. */
export function WorkspaceActions({ workspace }: { workspace: AdminWorkspaceDetail }) {
  const [opening, setOpening] = useState<Opening>(null);
  const close = () => setOpening(null);
  const suspended = workspace.status === "suspended";

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button variant="outline" size="sm" onClick={() => setOpening("seats")}>
        <Users aria-hidden="true" />
        Места: {formatNumber(workspace.plan.seats)}
      </Button>
      <Button variant="outline" size="sm" disabled={workspace.people.length < 2} onClick={() => setOpening("owner")}>
        <Crown aria-hidden="true" />
        Передать владение
      </Button>
      {suspended ? (
        <Button variant="outline" size="sm" onClick={() => void resume(workspace.id)}>
          <CirclePlay aria-hidden="true" />
          Восстановить доступ
        </Button>
      ) : (
        <Button variant="outline" size="sm" onClick={() => setOpening("suspend")}>
          <CirclePause aria-hidden="true" />
          Приостановить доступ
        </Button>
      )}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon-sm" aria-label="Другие действия">
            <EllipsisVertical />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          <DropdownMenuGroup>
            <DropdownMenuItem variant="destructive" onSelect={() => setOpening("delete")}>
              <Trash2 />
              Удалить пространство…
            </DropdownMenuItem>
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
      <SeatsDialog workspace={workspace} open={opening === "seats"} onClose={close} />
      <OwnerDialog workspace={workspace} open={opening === "owner"} onClose={close} />
      <SuspendDialog workspace={workspace} open={opening === "suspend"} onClose={close} />
      <DeleteDialog workspace={workspace} open={opening === "delete"} onClose={close} />
    </div>
  );
}
