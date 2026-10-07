"use client";

import { toast } from "sonner";

import { errorMessage } from "@/lib/errors";

import { settingsApi } from "../api/settings-api";
import type { DataKind } from "../domain/data-contract";
import { dataResources } from "./settings-resources";
import type { PrivacyWords } from "./words";

/** Unshares one link, or deletes one file or piece of feedback. */
export async function removeDataItem(kind: DataKind, id: string, t: PrivacyWords) {
  try {
    await settingsApi.deleteData(kind, id);
    dataResources[kind].update((data) => ({ items: data.items.filter((i) => i.id !== id) }));
  } catch (error) {
    toast.error(t("removeFailed"), { description: errorMessage(error) });
  }
}

/** Removes every item of the kind. */
export async function removeAllData(kind: DataKind, t: PrivacyWords) {
  try {
    await settingsApi.deleteAllData(kind);
    dataResources[kind].update(() => ({ items: [] }));
  } catch (error) {
    toast.error(t("removeAllFailed"), { description: errorMessage(error) });
  }
}
