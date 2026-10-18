"use client";

import { createContext, type ReactNode, use, useMemo, useState } from "react";

import { useTranslations } from "use-intl";

import { NameDialog, type NameRequest } from "@/components/name-dialog";
import { useSharedFiles } from "@/features/workspace/ui/personal/file-share-control";
import { useRouter } from "@/lib/navigation";

import type { FileFolder, FileItem, FilesResponse } from "../domain/contract";
import type { FileManagerView } from "../domain/files";
import { DEFAULT_FILTER, type FileFilter } from "../domain/filters";
import { folderHref, rootHref } from "../domain/paths";
import { renameFile } from "../model/file-actions";
import { createFolder, renameFolder } from "../model/folder-actions";
import { type FileActionWords, useFileActionWords } from "../model/words";
import { ShareDialog } from "./file-dialogs";

/** The grid/list choice in the current URL, so navigating between folders keeps it. Event handlers only. */
const currentView = (): FileManagerView =>
  new URLSearchParams(window.location.search).get("view") === "list" ? "list" : "grid";

type Workspace = { id: string; name: string };

type FileManagerActions = {
  /** Navigates to the folder's own page, or back to all files for `null`. */
  openFolder: (folderId: string | null) => void;
  renameFile: (file: FileItem) => void;
  renameFolder: (folder: FileFolder) => void;
  newFolder: () => void;
  share: (file: FileItem) => void;
};

type FileManagerContextValue = FilesResponse & {
  filter: FileFilter;
  setFilter: (filter: FileFilter) => void;
  /** Names of the workspaces each file is shared in, by file id. */
  sharedIn: (fileId: string) => Workspace[];
  actions: FileManagerActions;
};

const FileManagerContext = createContext<FileManagerContextValue | null>(null);

export function useFileManager() {
  const value = use(FileManagerContext);
  if (!value) throw new Error("useFileManager must be used inside <FileManagerProvider>");
  return value;
}

type Dialogs = {
  push: (href: string) => void;
  askName: (request: NameRequest) => void;
  share: (file: FileItem) => void;
};

/** The dialogs every page opens: naming and sharing in a workspace. */
function makeActions(
  { push, askName, share }: Dialogs,
  t: ReturnType<typeof useTranslations<"fileManager">>,
  words: FileActionWords,
): FileManagerActions {
  const { common } = words;
  return {
    openFolder: (folderId) => push(folderId ? folderHref(folderId, currentView()) : rootHref(currentView())),
    renameFile: (file) =>
      askName({
        title: t("dialogs.renameFile"),
        initial: file.name,
        submitLabel: common("actions.rename"),
        onSubmit: (name) => void renameFile(file.id, name, words),
      }),
    renameFolder: (folder) =>
      askName({
        title: t("dialogs.renameFolder"),
        initial: folder.name,
        submitLabel: common("actions.rename"),
        onSubmit: (name) => void renameFolder(folder, name, words),
      }),
    newFolder: () =>
      askName({
        title: t("folders.new"),
        initial: t("folders.untitled"),
        submitLabel: common("actions.create"),
        onSubmit: (name) => void createFolder(name, words),
      }),
    share,
  };
}

/** The loaded files with the dialogs every page shares: naming and sharing in a workspace. */
export function FileManagerProvider({ data, children }: { data: FilesResponse; children: ReactNode }) {
  const router = useRouter();
  const t = useTranslations("fileManager");
  const words = useFileActionWords();
  const shares = useSharedFiles();
  const [filter, setFilter] = useState(DEFAULT_FILTER);
  const [nameRequest, setNameRequest] = useState<NameRequest | null>(null);
  const [sharing, setSharing] = useState<FileItem | null>(null);

  const value = useMemo(() => {
    const dialogs = { push: router.push, askName: setNameRequest, share: setSharing };
    const actions = makeActions(dialogs, t, words);
    const sharedIn = (fileId: string) => (shares.get(fileId) ?? []).map((s) => s.workspace);
    return { ...data, filter, setFilter, sharedIn, actions };
  }, [data, filter, shares, router.push, t, words]);

  return (
    <FileManagerContext value={value}>
      {children}
      <NameDialog request={nameRequest} onClose={() => setNameRequest(null)} />
      <ShareDialog file={sharing} onClose={() => setSharing(null)} />
    </FileManagerContext>
  );
}
