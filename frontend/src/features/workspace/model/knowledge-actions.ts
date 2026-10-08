"use client";

import type { ReactNode } from "react";

import { toast } from "sonner";

import { apiErrorDescription } from "@/lib/api/error-description";

import type {
  ConnectSourceRequest,
  KnowledgeAccess,
  KnowledgeItem,
  KnowledgeUpdate,
  ShareFileRequest,
} from "../domain/knowledge-contract";
import { myKnowledgeResource, mySharesResource, resourcesOf } from "./resources";
import { failureText, words } from "./words";

const refreshMine = () => {
  void mySharesResource.refresh();
  void myKnowledgeResource.refresh();
};

/** Uploads files that belong to the workspace; resolves to null on success or the message for the dialog. */
export async function addKnowledge(
  ws: string,
  files: File[],
  access: KnowledgeAccess,
  projectId: string | null,
): Promise<string | null> {
  try {
    const { items } = await resourcesOf(ws).api.upload(files, access, projectId);
    resourcesOf(ws).knowledge.update((data) => ({ items: [...items, ...data.items] }));
    void myKnowledgeResource.refresh();
    const count = items.length;
    toast.success(
      words((t) => t("toasts.filesAdded", { count, name: items[0]?.name ?? "" })),
      {
        description: words((t) => t("toasts.filesAddedHint", { count })),
      },
    );
    return null;
  } catch (error) {
    return failureText(error);
  }
}

/** Connects a source for the workspace; resolves to null on success or the message for the dialog. */
export async function connectSource(ws: string, request: ConnectSourceRequest): Promise<string | null> {
  try {
    const item = await resourcesOf(ws).api.connectSource(request);
    resourcesOf(ws).knowledge.update((data) => ({ items: [item, ...data.items] }));
    toast.success(
      words((t) => t("toasts.sourceConnected", { name: item.name })),
      {
        description: words((t) => t("toasts.sourceConnectedHint")),
      },
    );
    return null;
  } catch (error) {
    return failureText(error);
  }
}

/** Who can use a piece of knowledge, or the project it belongs to. */
export async function changeKnowledge(ws: string, item: KnowledgeItem, update: KnowledgeUpdate, phrase: ReactNode) {
  try {
    const updated = await resourcesOf(ws).api.updateKnowledge(item.id, update);
    if (item.source.kind === "personal") void mySharesResource.refresh();
    void myKnowledgeResource.refresh();
    resourcesOf(ws).knowledge.update((data) => ({ items: data.items.map((i) => (i.id === item.id ? updated : i)) }));
    toast.success(phrase);
    return true;
  } catch (error) {
    toast.error(
      words((t) => t("toasts.knowledgeChangeFailed")),
      { description: apiErrorDescription(error) },
    );
    return false;
  }
}

export async function removeKnowledge(ws: string, item: KnowledgeItem) {
  const shared = item.source.kind === "personal";
  try {
    await resourcesOf(ws).api.removeKnowledge(item.id);
    resourcesOf(ws).knowledge.update((data) => ({ items: data.items.filter((i) => i.id !== item.id) }));
    refreshMine();
    const name = item.name;
    toast.success(
      words((t) => t(shared ? "toasts.stoppedSharing" : "toasts.knowledgeRemoved", { name })),
      {
        description: words((t) => t(shared ? "toasts.stoppedSharingHint" : "toasts.knowledgeRemovedHint")),
      },
    );
    return true;
  } catch (error) {
    toast.error(
      words((t) => t("toasts.knowledgeRemoveFailed")),
      { description: apiErrorDescription(error) },
    );
    return false;
  }
}

/** Shares (or re-scopes) one of the account's files in a workspace; it isn't copied. */
export async function shareFile(ws: string, request: ShareFileRequest, phrase: ReactNode) {
  try {
    await resourcesOf(ws).api.shareFile(request);
    refreshMine();
    void resourcesOf(ws).knowledge.refresh();
    toast.success(phrase, { description: words((t) => t("toasts.fileStaysYours", { count: 1 })) });
    return true;
  } catch (error) {
    toast.error(
      words((t) => t("toasts.shareFileFailed")),
      { description: apiErrorDescription(error) },
    );
    return false;
  }
}

/** Shares several of the account's files at once; resolves to null on success or the message for the dialog. */
export async function shareFiles(ws: string, requests: ShareFileRequest[]): Promise<string | null> {
  try {
    await Promise.all(requests.map((request) => resourcesOf(ws).api.shareFile(request)));
    refreshMine();
    void resourcesOf(ws).knowledge.refresh();
    const count = requests.length;
    toast.success(
      words((t) => t("toasts.filesShared", { count, name: requests[0]?.name ?? "" })),
      {
        description: words((t) => t("toasts.fileStaysYours", { count })),
      },
    );
    return null;
  } catch (error) {
    void resourcesOf(ws).knowledge.refresh();
    return failureText(error);
  }
}

/** Takes a shared file back out of a workspace; it stays in File Manager. */
export async function unshareFile(ws: string, itemId: string, name: string) {
  try {
    await resourcesOf(ws).api.removeKnowledge(itemId);
    refreshMine();
    void resourcesOf(ws).knowledge.refresh();
    toast.success(
      words((t) => t("toasts.stoppedSharing", { name })),
      {
        description: words((t) => t("toasts.stillInFileManager")),
      },
    );
    return true;
  } catch (error) {
    toast.error(
      words((t) => t("toasts.unshareFileFailed")),
      { description: apiErrorDescription(error) },
    );
    return false;
  }
}
