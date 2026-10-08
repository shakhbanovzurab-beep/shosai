"use client";

import { useTranslations } from "use-intl";

import { ConfirmDestructive } from "@/components/feedback";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ShareFileForm } from "@/features/workspace/ui/personal/share-file-form";

import type { FileItem } from "../domain/contract";
import { transferFile } from "../model/file-actions";
import { useFileActionWords } from "../model/words";

/** Shares a file in one of the account's workspaces; the workspace points to it, nothing is copied. */
export function ShareDialog({ file, onClose }: { file: FileItem | null; onClose: () => void }) {
  const t = useTranslations("fileManager");
  return (
    <Dialog open={file !== null} onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="sm:max-w-md">
        {file ? (
          <>
            <DialogHeader>
              <DialogTitle className="truncate" dir="auto">
                {t("dialogs.shareTitle", { name: file.name })}
              </DialogTitle>
              <DialogDescription>{t("dialogs.shareDescription")}</DialogDescription>
            </DialogHeader>
            <ShareFileForm file={file} onDone={onClose} />
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

type TransferRequest = { file: FileItem; workspace: { id: string; name: string } };

/** Hands a shared file over to the workspace for good, so it stays there when its owner leaves. */
export function TransferDialog({ request, onClose }: { request: TransferRequest | null; onClose: () => void }) {
  const t = useTranslations("fileManager");
  const words = useFileActionWords();
  const name = request?.file.name ?? "";
  const workspace = request?.workspace.name ?? "";
  return (
    <ConfirmDestructive
      open={request !== null}
      title={t("dialogs.transferTitle", { name, workspace })}
      description={t("dialogs.transferDescription", { workspace })}
      confirmLabel={t("dialogs.transfer")}
      onConfirm={() => {
        if (request) void transferFile(request.file, request.workspace, words);
        onClose();
      }}
      onCancel={onClose}
    />
  );
}
