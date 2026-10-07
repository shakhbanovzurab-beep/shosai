"use client";

import {
  ArrowRightLeft,
  Files,
  Folder,
  FolderInput,
  FolderOpen,
  HardDrive,
  Pencil,
  Share2,
  Star,
  StarOff,
  Trash2,
} from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";

import type { MenuKit } from "@/components/menu-kit";

import type { FileFolder, FileItem } from "../domain/contract";
import { folderStats } from "../domain/files";
import { deleteFile, duplicateFile, moveFile, setFileLeo, toggleStar } from "../model/file-actions";
import { deleteFolder, setFolderLeo } from "../model/folder-actions";
import { useFileActionWords } from "../model/words";
import { useFileManager } from "./file-manager-store";
import { useLeoBlocker } from "./leo-blocker";
import { LeoFileIcon } from "./leo-file-icon";

/** "Use with Leo" for a file: its own choice, unless its folder already decides or Leo can't read it. */
function LeoItem({ kit: K, file }: { kit: MenuKit; file: FileItem }) {
  const t = useTranslations("fileManager");
  const words = useFileActionWords();
  const { folders } = useFileManager();
  const blocked = useLeoBlocker()(file);
  const viaFolder = file.leo?.via === "folder" ? folders.find((f) => f.id === file.folder_id) : undefined;
  if (blocked || viaFolder)
    return (
      <K.Item disabled>
        <LeoFileIcon />
        <span className="flex flex-col">
          {t("menu.useWithLeo")}
          <span className="text-muted-foreground text-xs">
            {blocked ?? t("menu.usedThrough", { folder: viaFolder?.name ?? "" })}
          </span>
        </span>
      </K.Item>
    );
  return (
    <K.CheckboxItem checked={file.leo !== null} onCheckedChange={(on) => void setFileLeo(file, on === true, words)}>
      {t("menu.useWithLeo")}
    </K.CheckboxItem>
  );
}

/** Everything you can do to a file, as menu items for either kind of menu. */
export function FileMenuItems({ kit: K, file }: { kit: MenuKit; file: FileItem }) {
  const t = useTranslations("fileManager");
  const format = useFormatter();
  const words = useFileActionWords();
  const { common } = words;
  const { folders, sharedIn, actions } = useFileManager();
  const shared = sharedIn(file.id);
  const move = (folderId: string | null, name: string) => void moveFile(file, folderId, name, words);

  return (
    <>
      <K.Group>
        <K.Item onSelect={() => void toggleStar(file, words)}>
          {file.starred ? <StarOff /> : <Star />}
          {file.starred ? t("menu.removeStar") : t("menu.addStar")}
        </K.Item>
        <K.Item onSelect={() => actions.renameFile(file)}>
          <Pencil />
          {common("actions.renameMenu")}
        </K.Item>
        <K.Item onSelect={() => void duplicateFile(file, words)}>
          <Files />
          {common("actions.duplicate")}
        </K.Item>
        <K.Sub>
          <K.SubTrigger>
            <FolderInput />
            {t("menu.moveTo")}
          </K.SubTrigger>
          <K.SubContent className="w-48">
            <K.Item disabled={file.folder_id === null} onSelect={() => move(null, t("myFiles"))}>
              <HardDrive />
              {t("myFiles")}
            </K.Item>
            {folders.length > 0 ? <K.Separator /> : null}
            {folders.map((folder) => (
              <K.Item
                key={folder.id}
                disabled={file.folder_id === folder.id}
                onSelect={() => move(folder.id, folder.name)}
              >
                <Folder />
                <span className="truncate" dir="auto">
                  {folder.name}
                </span>
              </K.Item>
            ))}
          </K.SubContent>
        </K.Sub>
      </K.Group>
      <K.Separator />
      <K.Group>
        <LeoItem kit={K} file={file} />
        <K.Item disabled={!file.leo_readable} onSelect={() => actions.share(file)}>
          <Share2 />
          {shared.length ? t("menu.sharing") : t("menu.share")}
        </K.Item>
        {shared.length ? (
          <K.Sub>
            <K.SubTrigger>
              <ArrowRightLeft />
              {t("menu.transferTo")}
            </K.SubTrigger>
            <K.SubContent className="w-48">
              {shared.map((workspace) => (
                <K.Item key={workspace.id} onSelect={() => actions.transfer(file, workspace)}>
                  <span className="truncate" dir="auto">
                    {t("menu.transferWorkspace", { workspace: workspace.name })}
                  </span>
                </K.Item>
              ))}
            </K.SubContent>
          </K.Sub>
        ) : null}
      </K.Group>
      <K.Separator />
      <K.Group>
        <K.Item
          variant="destructive"
          onSelect={() => deleteFile(file, shared.length ? format.list(shared.map((w) => w.name)) : "", words)}
        >
          <Trash2 />
          {common("actions.delete")}
        </K.Item>
      </K.Group>
    </>
  );
}

/** Everything you can do to a folder, as menu items for either kind of menu. */
export function FolderMenuItems({ kit: K, folder }: { kit: MenuKit; folder: FileFolder }) {
  const t = useTranslations("fileManager");
  const words = useFileActionWords();
  const { common } = words;
  const { files, actions } = useFileManager();

  return (
    <>
      <K.Group>
        <K.Item onSelect={() => actions.openFolder(folder.id)}>
          <FolderOpen />
          {common("actions.open")}
        </K.Item>
        <K.Item onSelect={() => actions.renameFolder(folder)}>
          <Pencil />
          {common("actions.renameMenu")}
        </K.Item>
      </K.Group>
      <K.Separator />
      <K.Group>
        <K.CheckboxItem checked={folder.leo} onCheckedChange={(on) => void setFolderLeo(folder, on === true, words)}>
          {t("menu.useWithLeo")}
        </K.CheckboxItem>
      </K.Group>
      <K.Separator />
      <K.Group>
        <K.Item variant="destructive" onSelect={() => deleteFolder(folder, folderStats(folder, files).count, words)}>
          <Trash2 />
          {t("menu.deleteFolder")}
        </K.Item>
      </K.Group>
    </>
  );
}
