"use client";

import { useState, useTransition } from "react";

import { Folder } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { useFiles } from "@/features/file-manager/model/files-resource";
import { useFileActionWords } from "@/features/file-manager/model/words";
import { FilePicker } from "@/features/file-manager/ui/file-picker";
import { useLeoBlocker } from "@/features/file-manager/ui/leo-blocker";

import { chooseForLeo } from "../model/leo-files";

/** Mounted per opening, so each time starts with nothing picked. */
function ChooseFilesForm({ onDone }: { onDone: () => void }) {
  const t = useTranslations("knowledgeBase");
  const common = useTranslations("common");
  const words = useFileActionWords();
  const blocker = useLeoBlocker();
  const files = useFiles();
  const [picked, setPicked] = useState<ReadonlySet<string>>(new Set());
  const [pickedFolders, setPickedFolders] = useState<ReadonlySet<string>>(new Set());
  const [saving, startSaving] = useTransition();
  const folders = files.status === "ready" ? files.data.folders.filter((f) => !f.leo) : [];
  const toggle = (set: ReadonlySet<string>, id: string) => {
    const next = new Set(set);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    return next;
  };

  const save = () =>
    startSaving(async () => {
      if (files.status !== "ready") return;
      await chooseForLeo(
        files.data.folders.filter((f) => pickedFolders.has(f.id)),
        files.data.files.filter((f) => picked.has(f.id)),
        t,
        words,
      );
      onDone();
    });

  return (
    <div className="flex min-h-0 flex-col gap-4">
      <DialogHeader>
        <DialogTitle>{t("choose.title")}</DialogTitle>
        <DialogDescription>{t("choose.description")}</DialogDescription>
      </DialogHeader>
      {folders.length > 0 ? (
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 font-medium text-sm">{t("choose.folders")}</legend>
          <div className="flex flex-wrap gap-2">
            {folders.map((folder) => (
              <div
                key={folder.id}
                className="flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm has-[[data-state=checked]]:border-primary has-[[data-state=checked]]:bg-primary/5"
              >
                <Checkbox
                  id={`folder-${folder.id}`}
                  checked={pickedFolders.has(folder.id)}
                  onCheckedChange={() => setPickedFolders(toggle(pickedFolders, folder.id))}
                />
                <label htmlFor={`folder-${folder.id}`} className="flex cursor-pointer items-center gap-2">
                  <Folder className="size-4 text-muted-foreground" aria-hidden="true" />
                  <bdi>{folder.name}</bdi>
                </label>
              </div>
            ))}
          </div>
        </fieldset>
      ) : null}
      <FilePicker
        label={t("choose.files")}
        isSelected={(id) => picked.has(id)}
        onToggle={(file) => setPicked(toggle(picked, file.id))}
        unavailable={(file) => blocker(file) ?? (file.leo ? t("choose.alreadyUsed") : null)}
      />
      <DialogFooter>
        <Button variant="ghost" onClick={onDone}>
          {common("actions.cancel")}
        </Button>
        <Button disabled={saving || picked.size + pickedFolders.size === 0} onClick={save}>
          {saving ? <Spinner data-icon="inline-start" /> : null}
          {t("choose.submit")}
        </Button>
      </DialogFooter>
    </div>
  );
}

export function ChooseFilesDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[90dvh] flex-col sm:max-w-lg">
        {open ? <ChooseFilesForm onDone={() => onOpenChange(false)} /> : null}
      </DialogContent>
    </Dialog>
  );
}
