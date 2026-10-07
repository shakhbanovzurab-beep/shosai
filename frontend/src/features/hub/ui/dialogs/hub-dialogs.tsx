"use client";

import { useState } from "react";

import type { Hub } from "../../domain/contract";
import { ArchiveDialog } from "./archive-dialog";
import { BoardDialog } from "./board-dialog";
import { DeleteDialog } from "./delete-dialog";
import { NameDialog } from "./name-dialog";

/* One place that knows which hub dialog is open, shared by the list and the hub page. */

export type HubDialogKind = "rename" | "board" | "archive" | "delete";

export type HubDialogRequest = { kind: HubDialogKind; hub: Hub } | null;

export function useHubDialogs() {
  const [request, setRequest] = useState<HubDialogRequest>(null);
  return {
    request,
    open: (kind: HubDialogKind, hub: Hub) => setRequest({ kind, hub }),
    close: () => setRequest(null),
  };
}

export function HubDialogs({
  request,
  onClose,
  onDeleted,
}: {
  request: HubDialogRequest;
  onClose: () => void;
  onDeleted?: () => void;
}) {
  const hubFor = (kind: HubDialogKind) => (request?.kind === kind ? request.hub : null);
  const closeOn = (open: boolean) => (open ? undefined : onClose());
  return (
    <>
      <NameDialog hub={hubFor("rename")} open={request?.kind === "rename"} onOpenChange={closeOn} />
      <BoardDialog hub={hubFor("board")} onOpenChange={closeOn} />
      <ArchiveDialog hub={hubFor("archive")} onOpenChange={closeOn} />
      <DeleteDialog hub={hubFor("delete")} onOpenChange={closeOn} onDeleted={onDeleted} />
    </>
  );
}
