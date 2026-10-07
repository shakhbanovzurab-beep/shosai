"use client";

import { createContext, use } from "react";

import type { ShareableFile } from "../personal/share-file-form";

/**
 * The files picked to share in a workspace. The workspace owns the dialog; File Manager renders the
 * list of the account's files inside it and reads this to know what is picked.
 */
export type FileSelection = {
  isSelected: (fileId: string) => boolean;
  toggle: (file: ShareableFile) => void;
  /** Files already shared in this workspace, which the picker shows as such. */
  sharedHere: ReadonlySet<string>;
};

export const FileSelectionContext = createContext<FileSelection | null>(null);

/** Null outside the share dialog. */
export const useFileSelection = () => use(FileSelectionContext);
