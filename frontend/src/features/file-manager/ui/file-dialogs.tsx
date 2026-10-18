"use client";

import { useTranslations } from "use-intl";

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ShareFileForm } from "@/features/workspace/ui/personal/share-file-form";

import type { FileItem } from "../domain/contract";

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
