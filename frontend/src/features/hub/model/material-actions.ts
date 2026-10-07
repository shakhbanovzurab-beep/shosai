"use client";

import { toast } from "sonner";

import { hubApi } from "../api/hub-api";
import { errorCode } from "../api/hub-request";
import type { Loaded, Material } from "../domain/contract";
import { hubMaterials } from "./resources";
import { type ActionWords, errorText } from "./words";

/* Materials of a hub: add a link, upload a file, or take one out of the hub (the document itself stays). */

const listOf = (hubId: string) => hubMaterials.of(hubId);

function prepend(hubId: string, material: Material) {
  listOf(hubId).update((list: Loaded<Material[]>) => ({ ...list, data: [material, ...list.data] }));
}

/** Resolves to null when added, or the text to show in the form. */
export async function addLink(words: ActionWords, hubId: string, title: string, url: string) {
  try {
    prepend(hubId, await hubApi.addMaterial(hubId, { title: title.trim(), url: url.trim() }));
    toast.success(words.blocks("materials.added"), { description: title });
    return null;
  } catch (error) {
    return errorText(words.api, errorCode(error));
  }
}

/** Uploads the files side by side; each one that lands joins the list, each one refused says why. */
export async function uploadFiles(words: ActionWords, hubId: string, files: File[]) {
  await Promise.all(
    files.map(async (file) => {
      try {
        prepend(hubId, await hubApi.uploadMaterial(hubId, file));
        toast.success(words.blocks("materials.added"), { description: file.name });
      } catch (error) {
        toast.error(words.hub("saveFailed"), {
          description: words.blocks("materials.uploadFailed", {
            file: file.name,
            reason: errorText(words.api, errorCode(error)),
          }),
        });
      }
    }),
  );
}

export async function removeMaterial(words: ActionWords, hubId: string, material: Material) {
  const without = (list: Loaded<Material[]>) => ({ ...list, data: list.data.filter((m) => m.id !== material.id) });
  listOf(hubId).update(without);
  try {
    await hubApi.removeMaterial(hubId, material.id);
    toast.success(words.blocks("materials.removed"), { description: material.title });
  } catch (error) {
    void listOf(hubId).refresh();
    toast.error(words.hub("saveFailed"), { description: errorText(words.api, errorCode(error)) });
  }
}
