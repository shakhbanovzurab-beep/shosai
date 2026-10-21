"use client";

import { useState } from "react";

import { FolderOpen } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import type { FileItem } from "@/features/file-manager/domain/contract";
import { FilePicker } from "@/features/file-manager/ui/file-picker";

/** «Из моих файлов»: отметить файлы File Manager; в задачу уходят их копии (FL-D4), оригиналы остаются на месте. */
export function FromFilesDialog({ disabled, onAttach }: { disabled: boolean; onAttach: (files: FileItem[]) => void }) {
  const t = useTranslations("kanbanPanel");
  const [open, setOpen] = useState(false);
  const [picked, setPicked] = useState<Map<string, FileItem>>(() => new Map());
  const toggle = (file: FileItem) =>
    setPicked((current) => {
      const next = new Map(current);
      if (next.has(file.id)) next.delete(file.id);
      else next.set(file.id, file);
      return next;
    });
  const change = (next: boolean) => {
    setOpen(next);
    if (!next) setPicked(new Map());
  };
  return (
    <Dialog open={open} onOpenChange={change}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" disabled={disabled}>
          <FolderOpen data-icon="inline-start" />
          {t("attachments.fromFiles")}
        </Button>
      </DialogTrigger>
      <DialogContent className="flex max-h-[85dvh] flex-col sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t("attachments.picker.title")}</DialogTitle>
          <DialogDescription>{t("attachments.picker.hint")}</DialogDescription>
        </DialogHeader>
        <FilePicker label={t("attachments.picker.label")} isSelected={(id) => picked.has(id)} onToggle={toggle} />
        <DialogFooter>
          <Button
            disabled={picked.size === 0}
            onClick={() => {
              onAttach([...picked.values()]);
              change(false);
            }}
          >
            {t("attachments.picker.attach", { count: picked.size })}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
